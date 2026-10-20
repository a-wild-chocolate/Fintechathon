import asyncio
import json
import os
import logging
import httpx
from typing import Literal
from pydantic import BaseModel, Field, ValidationError
from ..models import ModelClient, ModelOutputError, ROLES
from .mcp_client import connect
from .store import AgentStore
from .workflows import Workflows, Workspace
from .human import Question, question_cards

class CallBudgetExceeded(ValueError):
    pass

def failure_reason(exc):
    if isinstance(exc, BaseExceptionGroup):
        return failure_reason(exc.exceptions[0])
    if isinstance(exc, ModelOutputError): return exc.reason
    if isinstance(exc, ValidationError): return 'invalid_result'
    if isinstance(exc, CallBudgetExceeded): return 'call_budget'
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429: return 'rate_limited'
    if isinstance(exc, httpx.HTTPError): return 'model_connection'
    return 'execution_error'

class Paragraph(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
    sources: list[int] = Field(default_factory=list)

class Result(BaseModel):
    status: Literal['completed', 'needs_information', 'needs_approval']
    paragraphs: list[Paragraph] = Field(max_length=4)
    follow_up: str = Field(default='', max_length=2000)
    questions: list[Question] = Field(default_factory=list, max_length=3)

class AgentRuntime:
    def __init__(self, library, model=None, connector=None):
        self.library = library
        self.tenant = library.settings.tenant
        self.store = AgentStore(library.root / 'agents.sqlite3')
        self.workflows = Workflows(library, self.store)
        self.model = model or ModelClient()
        self.connector = connector or connect
        # A process restart cannot resume an in-flight provider request safely.
        with self.store.db.connect(write=True) as db:
            db.execute("UPDATE agent_runs SET status='interrupted' WHERE status='running'")

    def for_company(self, tenant):
        from copy import copy
        from dataclasses import replace
        scoped = copy(self)
        scoped.tenant = tenant
        scoped.library = copy(self.library)
        scoped.library.settings = replace(self.library.settings, tenant=tenant)
        scoped.workflows = Workflows(scoped.library, self.store)
        return scoped

    @property
    def enabled(self):
        return os.getenv('TRADEX_AGENTS_ENABLED', '0') == '1' and self.model.configured

    def status(self):
        return {'harness': 'deepagents', 'mode': 'multi_agent' if self.enabled else 'evidence', 'provider': self.model.provider,
                'web_search_enabled': os.getenv('TRADEX_WEB_ENABLED', '0') == '1',
                'sandbox_enabled': os.getenv('TRADEX_SANDBOX_ENABLED', '0') == '1', 'models': self.model.models, 'roles': list(ROLES), 'configured': self.model.configured}

    def prepare(self, question, language='zh', document_id=None, order_id=None, history=None, session_id=None, workspace=None, market=None, analysis_only=False):
        if document_id:
            doc = self.library.document(document_id, self.tenant)
            if order_id and doc['tenant'] != 'public' and doc['metadata'].get('order_id') not in {None, '', order_id}:
                raise ValueError('Document belongs to a different order')
        if workspace:
            snapshot = Workspace.model_validate(workspace).model_dump()
            self.store.import_workspace(self.tenant, snapshot)
        request = {'question': question, 'language': language, 'document_id': document_id,
                   'order_id': order_id, 'session_id': session_id, 'market': market, 'analysis_only': analysis_only}
        run_id, session_id, prior = self.store.start(self.tenant, request)
        return run_id, session_id, request, prior

    def answer(self, question, **kwargs):
        return self.execute(*self.prepare(question, **kwargs))

    def execute(self, run_id, session_id, request, prior):
        language = request['language']
        turn = Turn(self, run_id, request, prior)
        try:
            output = asyncio.run(turn.execute())
            task_status = output.pop('status')
        except Exception as exc:
            reason = failure_reason(exc)
            cause = exc
            while isinstance(cause, BaseExceptionGroup): cause = cause.exceptions[0]
            self.store.append(run_id, self.tenant, {'event': 'failure', 'error_type': type(cause).__name__,
                                                  'reason': reason, 'agent': getattr(cause, 'role', None)})
            logging.getLogger(__name__).exception('Agent run %s failed (%s)', run_id, reason)
            messages = {
                'call_budget': ('本轮调用次数已达到上限，已保留完成的子任务结果。', 'This turn reached its call limit. Completed specialist results are preserved.'),
                'rate_limited': ('模型服务请求限流。已确认的付款和资金数据已保存，请稍后点击重新分析。', 'The model service is rate-limiting requests. Saved payment and cash data are unchanged. Please retry the analysis shortly.'),
                'model_connection': ('模型连接未完成，已保留执行记录。', 'The model connection did not complete. Execution records are preserved.'),
                'output_truncated': ('模型输出达到长度上限，结果未能完整返回。已保留完成的步骤。', 'The model reached its output limit before returning a complete result. Completed steps are preserved.'),
                'invalid_tool_arguments': ('模型返回的工具参数格式不完整，未执行该操作。', 'The model returned invalid tool arguments; that operation was not executed.'),
                'missing_result': ('智能体未提交可读取的结果，已保留完成的步骤。', 'The agent did not submit a readable result. Completed steps are preserved.'),
                'invalid_result': ('智能体结果未通过字段或格式检查，已保留完成的步骤。', 'The agent result failed field or format validation. Completed steps are preserved.'),
                'execution_error': ('本轮执行未完成，已保留完成的子任务结果与执行记录。', 'Execution did not complete. Completed specialist results and activity are preserved.'),
            }
            output = {'paragraphs': [p for result in turn.outputs.values() for p in result['paragraphs']],
                      'follow_up': messages[reason][language == 'en'], 'failure_reason': reason}
            task_status = 'failed'
        proposal = None if request.get('analysis_only') else self.store.proposal(self.tenant, session_id)
        if task_status != 'failed' and proposal and proposal['status'] in {'needs_information', 'needs_approval'}:
            task_status = proposal['status']
        elif task_status == 'needs_approval':
            task_status = 'completed'
        if output.get('questions') and task_status != 'failed':
            task_status = 'needs_information'
        output['questions'] = question_cards(output, proposal, language, turn.outputs, request.get('human_answers', [])) if task_status == 'needs_information' else []
        saved = self.store.run(run_id, self.tenant)
        result = dict(output, mode='multi_agent', model=self.model.models['coordinator'], provider=self.model.provider,
                      task_status=task_status, run_id=run_id, session_id=session_id,
                      sources=saved['sources'], proposal=proposal, trace=saved['trace'],
                      specialist_results=turn.outputs, workflow_facts=turn.facts, specialist_sources=turn.dependencies,
                      workspace=self.store.workspace(self.tenant))
        self.store.finish(run_id, self.tenant, result)
        return result

class Turn:
    def __init__(self, runtime, run_id, request, history):
        self.runtime, self.run_id, self.request = runtime, run_id, request
        self.history = history
        self.remaining = int(os.getenv('TRADEX_AGENT_MAX_CALLS', '18'))
        self.outputs = {}
        self.facts = {}
        self.dependencies = {}
        self.tool_cache = {}
        self.continuation = None
        self.delegations = 0
        self.delegation_lock = asyncio.Lock()

    def record(self, entry):
        self.runtime.store.append(self.run_id, self.runtime.tenant, entry)

    def checked_result(self, value):
        result = Result.model_validate(value).model_dump()
        known = {s['id'] for s in self.runtime.store.run(self.run_id, self.runtime.tenant)['sources']}
        if any(not set(p['sources']) <= known for p in result['paragraphs']): raise ValueError('Unknown source reference')
        return result

    async def execute(self):
        # Carry versioned source references across clarification turns.
        if self.request.get('reply_to_run_id'):
            from .continuation import Continuation
            parent = self.runtime.store.run(self.request['reply_to_run_id'], self.runtime.tenant)
            self.runtime.store.sources(self.run_id, self.runtime.tenant, parent['result'].get('sources', []))
            self.continuation = Continuation(self, parent)
        else:
            for turn in self.history:
                self.runtime.store.sources(self.run_id, self.runtime.tenant, turn['answer'].get('sources', []))
        async with self.runtime.connector(self.run_id) as client:
            self.client = client
            return await self.agent('coordinator', self.request['question'])

    async def agent(self, role, task):
        from .harness import run_agent
        return await run_agent(self, role, task)
