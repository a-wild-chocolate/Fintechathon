"""Deep Agents orchestration over TradeX's provider and MCP adapters."""
import asyncio
import json
from typing import Any
from deepagents import create_deep_agent
from deepagents.profiles import HarnessProfile, GeneralPurposeSubagentProfile, register_harness_profile
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, convert_to_openai_messages
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from .prompts import COMMON, ROLES
from ..models import ModelOutputError

register_harness_profile('tradex:business', HarnessProfile(
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    excluded_tools=frozenset({'ls', 'read_file', 'write_file', 'edit_file', 'glob', 'grep', 'execute', 'write_todos'})))

class BusinessModel(BaseChatModel):
    turn: Any
    role: str
    model_name: str = 'tradex:business'
    calls: int = 0

    @property
    def _llm_type(self): return 'tradex'

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[convert_to_openai_tool(tool) for tool in tools])

    def _generate(self, messages, **kwargs):
        raise NotImplementedError('TradeX executes agents asynchronously.')

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        from .runtime import CallBudgetExceeded
        reserve = int(self.role != 'coordinator')
        limit = 7 if self.role == 'coordinator' else 5
        if self.turn.remaining <= reserve or self.calls >= limit:
            raise CallBudgetExceeded('Agent model-call budget exhausted')
        tools = kwargs['tools']
        if self.calls == limit - 1 or self.turn.remaining == reserve + 1:
            tools = [tool for tool in tools if tool['function']['name'] == 'finish']
        self.calls += 1
        self.turn.remaining -= 1
        self.turn.record({'event': 'model_started', 'agent': self.role})
        message, usage = await asyncio.to_thread(self.turn.runtime.model.chat, self.role,
                                                 convert_to_openai_messages(messages), tools)
        self.turn.record({'event': 'model_call', 'agent': self.role, **usage})
        if usage.get('finish_reason') == 'length':
            raise ModelOutputError('output_truncated', self.role)
        try:
            calls = [{'name': call['function']['name'], 'args': json.loads(call['function']['arguments']), 'id': call['id']}
                     for call in message.get('tool_calls', [])]
        except json.JSONDecodeError as exc:
            raise ModelOutputError('invalid_tool_arguments', self.role) from exc
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=message.get('content') or '', tool_calls=calls))])

def workflow_tool(turn, role, definition):
    spec = definition['function']
    async def invoke(**arguments):
        name = spec['name']
        turn.record({'event': 'tool_started', 'agent': role, 'tool': name})
        try:
            value = await turn.client.call(role, name, arguments)
        except ValueError as exc:
            turn.record({'event': 'tool_error', 'agent': role, 'tool': name, 'error': str(exc)})
            return {'error': str(exc)}
        turn.record({'event': 'tool_result', 'agent': role, 'tool': name, 'arguments': arguments, 'result': value})
        if name == 'wf_cash':
            return {key: item for key, item in value.items() if key != 'daily_balances'}
        if name == 'wf_options' and 'candidate' in value:
            return {**value, **{key: {field: item for field, item in value[key].items() if field != 'daily_balances'}
                               for key in ('current', 'candidate')}}
        return value
    return StructuredTool(name=spec['name'], description=spec.get('description', spec['name']),
                          args_schema=spec['parameters'], coroutine=invoke)

async def run_agent(turn, role, task):
    from .runtime import Result, CallBudgetExceeded
    turn.record({'event': 'agent_started', 'agent': role})
    completed = {}
    async def finish(**arguments):
        turn.record({'event': 'tool_started', 'agent': role, 'tool': 'finish'})
        completed.update(turn.checked_result(arguments))
        turn.record({'event': 'tool_result', 'agent': role, 'tool': 'finish', 'status': completed['status']})
        return json.dumps(completed, ensure_ascii=False)
    tools = [workflow_tool(turn, role, definition) for definition in turn.client.definitions(role)]
    tools.append(StructuredTool(name='finish', description='Return this role result and clarification questions.',
                                args_schema=Result, coroutine=finish, return_direct=True))
    subagents = []
    if role == 'coordinator':
        async def delegate(state, child):
            async with turn.delegation_lock:
                if turn.delegations >= 4 or turn.remaining < 2:
                    raise CallBudgetExceeded('Delegation budget exhausted')
                turn.delegations += 1
                turn.record({'event': 'tool_started', 'agent': role, 'tool': 'task'})
                result = await run_agent(turn, child, state['messages'][-1].content)
                turn.outputs[child] = result
                turn.record({'event': 'tool_result', 'agent': role, 'tool': 'task', 'result': {'agent': child, 'status': result['status']}})
                return {'messages': [AIMessage(content=json.dumps(result, ensure_ascii=False))]}
        for child in ('reconciliation', 'cash_flow', 'decision'):
            async def invoke(state, child=child): return await delegate(state, child)
            subagents.append({'name': child, 'description': ROLES[child], 'runnable': RunnableLambda(invoke)})
    agent = create_deep_agent(model=BusinessModel(turn=turn, role=role), tools=tools,
                              system_prompt=COMMON + ROLES[role], subagents=subagents, name=role)
    context = {'request': turn.request, 'task': task, 'specialist_results': turn.outputs,
               'recent_turns': [{'question': item['question'], 'questions': item['answer'].get('questions', [])}
                                for item in turn.history],
               'known_sources': [{key: source[key] for key in ('id', 'document_id', 'version', 'title', 'locator') if key in source}
                                 for source in turn.runtime.store.run(turn.run_id, turn.runtime.tenant)['sources']]}
    result = await agent.ainvoke({'messages': [{'role': 'user', 'content': json.dumps(context, ensure_ascii=False)}]},
                                 {'recursion_limit': 30})
    if not completed:
        try:
            payload = json.loads(result['messages'][-1].content)
        except json.JSONDecodeError as exc:
            raise ModelOutputError('missing_result', role) from exc
        completed.update(turn.checked_result(payload))
    turn.record({'event': 'agent_finished', 'agent': role, 'status': completed['status']})
    return completed
