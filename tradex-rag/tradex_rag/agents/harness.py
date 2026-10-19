"""Deep Agents orchestration over CashWeave's provider and MCP adapters."""
import asyncio
import json
from typing import Any
from pydantic import BaseModel, Field
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
    excluded_tools=frozenset({'ls', 'read_file', 'write_file', 'edit_file', 'glob', 'grep', 'execute', 'delete', 'write_todos'})))

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
        raise NotImplementedError('CashWeave executes agents asynchronously.')

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        from .runtime import CallBudgetExceeded
        reserve = int(self.role != 'coordinator' and not self.turn.continuation)
        limit = 7 if self.role == 'coordinator' else 5
        if self.turn.remaining <= reserve or self.calls >= limit:
            raise CallBudgetExceeded('Agent model-call budget exhausted')
        tools = kwargs['tools']
        if self.role == 'coordinator' and self.turn.continuation and not self.turn.continuation.planned:
            tools = [tool for tool in tools if tool['function']['name'] == 'plan_resume']
        elif self.calls == limit - 1 or self.turn.remaining == reserve + 1:
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
        cache_key = None
        if name in {'wf_status', 'wf_cash', 'wf_options'}:
            from .continuation import CashScenario
            store, tenant = turn.runtime.store, turn.runtime.tenant
            workspace = store.workspace(tenant)
            run = store.run(turn.run_id, tenant)
            proposal = store.proposal(tenant, run['session_id'])
            normalized = CashScenario.model_validate(arguments).model_dump() if name != 'wf_status' else arguments
            cache_key = json.dumps([name, normalized, workspace, proposal], sort_keys=True)
            if name == 'wf_cash' and turn.continuation and workspace == turn.continuation.workspace and proposal == turn.continuation.proposal:
                for fact in turn.continuation.cash_facts:
                    if fact['arguments'] == normalized:
                        turn.tool_cache[cache_key] = fact['result']
            if cache_key in turn.tool_cache:
                turn.record({'event': 'workflow_reused', 'agent': role, 'tool': name})
                return turn.tool_cache[cache_key]
        turn.record({'event': 'tool_started', 'agent': role, 'tool': name})
        try:
            value = await turn.client.call(role, name, arguments)
        except ValueError as exc:
            turn.record({'event': 'tool_error', 'agent': role, 'tool': name, 'error': str(exc)})
            return {'error': str(exc)}
        turn.record({'event': 'tool_result', 'agent': role, 'tool': name, 'arguments': arguments, 'result': value})
        if name in {'kb_search', 'evidence_read'}:
            dependencies = turn.dependencies.setdefault(role, {})
            for source in value.get('sources', []):
                dependencies[source['document_id']] = source['version']
        if name == 'wf_cash':
            value = {key: item for key, item in value.items() if key != 'daily_balances'}
        if name == 'wf_options' and 'candidate' in value:
            value = {**value, **{key: {field: item for field, item in value[key].items() if field != 'daily_balances'}
                                for key in ('current', 'candidate')}}
        if name in {'wf_status', 'wf_cash', 'wf_options', 'wf_reconcile'}:
            turn.facts.setdefault(role, []).append({'tool': name, 'arguments': arguments, 'result': value})
        if cache_key and 'error' not in value and value.get('status') != 'needs_information':
            turn.tool_cache[cache_key] = value
        return value
    return StructuredTool(name=spec['name'], description=spec.get('description', spec['name']),
                          args_schema=spec['parameters'], coroutine=invoke)

async def run_agent(turn, role, task):
    from .runtime import Result, CallBudgetExceeded
    from .continuation import ResumePlan, SPECIALISTS
    class Draft(BaseModel):
        kind: str = Field(min_length=1, max_length=80)
        text: str = Field(min_length=1, max_length=4000, description='Full ready-to-review correspondence, normally 100-180 words.')
    class DecisionResult(Result):
        draft: Draft | None = Field(default=None, description='Optional draft to save together with this reply; never sends anything.')
    class DraftResult(Result):
        draft: Draft
    class ResumeReply(ResumePlan):
        response: Result | None = Field(default=None, description='Final reply when no specialist is needed. Otherwise leave null; the scheduler runs the selected roles and returns their answer.')
    turn.record({'event': 'agent_started', 'agent': role})
    completed = {}
    completion_lock = asyncio.Lock()
    async def finish(**arguments):
        async with completion_lock:
            if completed:
                return json.dumps(completed, ensure_ascii=False)
            turn.record({'event': 'tool_started', 'agent': role, 'tool': 'finish'})
            draft = arguments.pop('draft', None)
            result = turn.checked_result(arguments)
            if draft:
                definition = next(d for d in turn.client.definitions(role) if d['function']['name'] == 'wf_draft')
                saved = await workflow_tool(turn, role, definition).ainvoke(Draft.model_validate(draft).model_dump())
                if 'error' in saved:
                    raise ValueError(saved['error'])
            completed.update(result)
            turn.record({'event': 'tool_result', 'agent': role, 'tool': 'finish', 'status': completed['status']})
            return json.dumps(completed, ensure_ascii=False)
    definitions = turn.client.definitions(role)
    if role == 'decision':
        definitions = [d for d in definitions if d['function']['name'] != 'wf_draft']
    if turn.continuation:
        supplied = {'wf_status'}
        if role == 'decision' and turn.facts.get('cash_flow'):
            supplied.add('wf_cash')
        definitions = [d for d in definitions if d['function']['name'] not in supplied]
        if role == 'decision' and turn.continuation.decision_task == 'draft':
            definitions = []
    tools = [workflow_tool(turn, role, definition) for definition in definitions]
    result_schema = DecisionResult if role == 'decision' else Result
    if role == 'decision' and turn.continuation and turn.continuation.decision_task == 'draft':
        result_schema = DraftResult
    tools.append(StructuredTool(name='finish', description='Return this role result and clarification questions.',
                                args_schema=result_schema, coroutine=finish, return_direct=True))
    subagents = []
    if role == 'coordinator':
        if turn.continuation:
            async def plan_resume(response=None, **arguments):
                async with completion_lock:
                    if completed:
                        return json.dumps(completed, ensure_ascii=False)
                    plan = turn.continuation.plan(**arguments)
                    selected = [child for child in SPECIALISTS if child in plan['rerun_roles']]
                    if not selected:
                        completed.update(turn.checked_result(response))
                    for child in selected:
                        if turn.remaining < 1:
                            raise CallBudgetExceeded('Continuation budget exhausted')
                        turn.record({'event': 'tool_started', 'agent': role, 'tool': 'task'})
                        result = await run_agent(turn, child, 'Continue the original task using the supplied human answers and current workflow facts. '+arguments['reason'])
                        turn.outputs[child] = result
                        completed.update(result)
                        turn.record({'event': 'tool_result', 'agent': role, 'tool': 'task', 'result': {'agent': child, 'status': result['status']}})
                        if result['status'] != 'completed':
                            break
                    turn.record({'event': 'response_ready', 'agent': role, 'status': completed['status']})
                    return json.dumps(completed, ensure_ascii=False)
            tools = [StructuredTool(name='plan_resume', description='Plan and execute this continuation once. Selected specialists run automatically; their final answer is delivered without another coordinator call. For no specialist, supply response.',
                                    args_schema=ResumeReply, coroutine=plan_resume, return_direct=True)]
        async def delegate(state, child):
            async with turn.delegation_lock:
                if turn.continuation:
                    if not turn.continuation.planned:
                        return {'messages': [AIMessage(content='Call plan_resume before delegating a clarification.') ]}
                    if child in turn.outputs and turn.outputs[child]['status'] == 'completed':
                        turn.record({'event': 'agent_reused', 'agent': child, 'from_run_id': turn.continuation.parent['id'] if child not in turn.continuation.rerun else turn.run_id})
                        return {'messages': [AIMessage(content=json.dumps(turn.outputs[child], ensure_ascii=False))]}
                    if child not in turn.continuation.rerun:
                        return {'messages': [AIMessage(content='This specialist is outside the continuation plan; use the available results and finish.') ]}
                if turn.delegations >= 4 or turn.remaining < 2:
                    raise CallBudgetExceeded('Delegation budget exhausted')
                turn.delegations += 1
                turn.record({'event': 'tool_started', 'agent': role, 'tool': 'task'})
                result = await run_agent(turn, child, state['messages'][-1].content)
                turn.outputs[child] = result
                turn.record({'event': 'tool_result', 'agent': role, 'tool': 'task', 'result': {'agent': child, 'status': result['status']}})
                return {'messages': [AIMessage(content=json.dumps(result, ensure_ascii=False))]}
        for child in (() if turn.continuation else ('reconciliation', 'cash_flow', 'decision')):
            async def invoke(state, child=child): return await delegate(state, child)
            subagents.append({'name': child, 'description': ROLES[child], 'runnable': RunnableLambda(invoke)})
    agent = create_deep_agent(model=BusinessModel(turn=turn, role=role), tools=tools,
                              system_prompt=COMMON + ROLES[role], subagents=subagents, name=role)
    context = {'request': turn.request, 'task': task, 'specialist_results': turn.outputs,
               'workflow_facts': turn.facts,
               'continuation': turn.continuation.context() if turn.continuation else None,
               'recent_turns': [{'question': item['question'], 'questions': item['answer'].get('questions', [])}
                                for item in turn.history],
               'known_sources': [{key: source[key] for key in ('id', 'document_id', 'version', 'title', 'locator') if key in source}
                                 for source in turn.runtime.store.run(turn.run_id, turn.runtime.tenant)['sources']]}
    if turn.continuation:
        context['request'] = {key: value for key, value in turn.request.items() if key not in {'original_question', 'question'}}
        context['request']['question'] = 'Apply the human answers to the original task.'
        context['recent_turns'] = []
        if role != 'coordinator':
            context['continuation'] = {key: value for key, value in context['continuation'].items()
                                       if key in {'original_question', 'current_workspace', 'current_proposal', 'required_roles', 'cash_scenarios'}}
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
