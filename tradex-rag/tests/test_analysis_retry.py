import httpx
import pytest
from types import SimpleNamespace
from tradex_rag.agents.runtime import failure_reason
from tradex_rag.agents.workflows import Workflows
from tradex_rag.service import Conflict


def test_rate_limit_is_distinct_from_connection_failure():
    response = httpx.Response(429, request=httpx.Request('POST', 'https://example.com'))
    error = httpx.HTTPStatusError('Limited', request=response.request, response=response)
    assert failure_reason(error) == 'rate_limited'
    assert failure_reason(ExceptionGroup('wrapped', [error])) == 'rate_limited'


@pytest.mark.parametrize('role,tool', [('reconciliation', 'wf_reconcile'), ('decision', 'wf_draft'), ('decision', 'sandbox_python')])
def test_analysis_retry_blocks_write_tools(role, tool):
    flow = object.__new__(Workflows)
    flow.tenant = 'test'
    flow.store = SimpleNamespace(run=lambda *args: {'request': {'analysis_only': True}, 'status': 'running'})
    with pytest.raises(Conflict, match='Analysis-only'):
        flow.execute(tool, 'run', role, {})


def test_coordinator_delivers_clarification_without_model_call():
    import asyncio
    from tradex_rag.agents.harness import BusinessModel
    answer = {'status': 'needs_information', 'paragraphs': [], 'questions': [], 'follow_up': 'What date?'}
    turn = SimpleNamespace(continuation=None, outputs={'reconciliation': answer}, record=lambda event: None)
    model = BusinessModel(turn=turn, role='coordinator')
    result = asyncio.run(model._agenerate([]))
    assert result.generations[0].message.tool_calls[0]['args'] == answer
    assert model.calls == 0
