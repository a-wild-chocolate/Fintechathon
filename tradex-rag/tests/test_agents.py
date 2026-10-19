import json
from contextlib import asynccontextmanager
import httpx
import pytest
from tradex_rag.config import Settings
from tradex_rag.service import Library, Conflict
from tradex_rag.models import ModelClient
from tradex_rag.agents.runtime import AgentRuntime
from tradex_rag.agents.workflows import ALLOW, cash
from test_library import TestEmbedding, add

SNAPSHOT = {'version': 1, 'opening': 128000, 'supplierDay': 5, 'receiptDay': 12, 'amountUSD': 12000}

def call(name, **args):
    return {'id': name, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}

def finish(status='completed', sources=None):
    return call('finish', status=status, paragraphs=[{'text': 'Evidence and financial analysis.', 'sources': sources or []}],
                follow_up='Please confirm the missing fields.' if status != 'completed' else '')

class ScriptedModel:
    """Provider substitute only; business workflows and LangGraph are real."""
    configured = True
    provider = 'test'
    models = {role: 'fixture' for role in ALLOW}
    def __init__(self, doc_id): self.doc_id = doc_id; self.calls = []
    def chat(self, role, messages, tools):
        context = json.loads(messages[1]['content']); question = context['request']['question']
        if context['request'].get('human_answers'):
            comments = [a['comment'] for a in context['request']['human_answers'] if a['comment']]
            question = comments[-1] if comments else 'read email'
        n = sum(m['role'] == 'assistant' for m in messages)
        self.calls.append(role)
        if role == 'coordinator':
            if n == 0: calls = [call('wf_status')]
            elif n == 1: calls = [call('task', subagent_type='cash_flow' if question == 'confirmed' else 'reconciliation', description=question)]
            elif n == 2 and question == 'confirmed': calls = [call('task', subagent_type='decision', description='Compare a 10 day extension and draft a request')]
            else: calls = [finish('completed' if question == 'confirmed' else 'needs_approval' if question == '2026-10-29' else 'needs_information', [1])]
        elif role == 'reconciliation':
            if n == 0: calls = [call('wf_status'), call('evidence_read', document_id=self.doc_id)]
            elif n == 1: calls = [call('wf_reconcile', amount_usd=6000 if question != 'read email' else None,
                                      receipt_date='2026-10-29' if question == '2026-10-29' else None, evidence_ids=[1])]
            else: calls = [finish('needs_approval' if question == '2026-10-29' else 'needs_information', [1])]
        elif role == 'cash_flow': calls = [call('wf_cash')] if n == 0 else [finish()]
        else: calls = [call('wf_options', supplier_extension_days=10), call('wf_draft', kind='supplier_request', text='Could we extend the payment deadline?')] if n == 0 else [finish()]
        return {'role': 'assistant', 'content': None, 'tool_calls': calls}, {'model': 'fixture', 'usage': {'total_tokens': 10}}

@pytest.fixture
def setup(tmp_path):
    library = Library(Settings(data_dir=tmp_path, tenant='test'), embedding=TestEmbedding())
    doc = add(library, 'We will pay the undisputed portion first. The rest follows quality review.', tenant='test', metadata={'order_id': 'TF-26104'})['document_id']
    model = ScriptedModel(doc); runtime = AgentRuntime(library, model=model)
    @asynccontextmanager
    async def connector(run_id):
        class Client:
            def definitions(self, role):
                return [{'type':'function','function':{'name':name,'parameters':{'type':'object','properties':{}}}} for name in ALLOW[role]]
            async def call(self, role, name, args): return runtime.workflows.execute(name, run_id, role, args)
        yield Client()
    runtime.connector = connector
    yield library, runtime, model, doc
    library.close()

def test_clarification_confirmation_and_specialist_handoffs(setup):
    _, runtime, model, doc = setup
    first = runtime.answer('read email', language='en', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    assert first['task_status'] == 'needs_information', first
    assert first['proposal']['missing_fields'] == ['amount_usd', 'receipt_date']
    session = first['session_id']
    second = runtime.answer('6000', language='en', order_id='TF-26104', document_id=doc, session_id=session)
    assert second['proposal']['missing_fields'] == ['receipt_date']
    third = runtime.answer('2026-10-29', language='en', order_id='TF-26104', document_id=doc, session_id=session)
    assert third['task_status'] == 'needs_approval'
    assert runtime.store.workspace('test')['amountUSD'] == 12000
    result = runtime.workflows.confirm(third['proposal']['id'])
    assert result['workspace']['version'] == 2 and result['workspace']['amountUSD'] == 6000
    assert result['after']['peak_shortfall_cny'] == 34000
    assert result['after']['first_shortfall']['balance_cny'] == -32000
    assert result['actual_cash_changed'] is False and result['workspace']['opening'] == 128000
    assert runtime.workflows.confirm(third['proposal']['id']) == result
    last = runtime.answer('confirmed', order_id='TF-26104', document_id=doc, session_id=session)
    assert last['task_status'] == 'completed'
    assert {'coordinator','reconciliation','cash_flow','decision'} <= set(model.calls)
    assert any(t.get('tool') == 'wf_draft' for t in last['trace'])
    assert runtime.store.run(last['run_id'],'test')['status'] == 'completed'
    assert last['sources'][0]['version'] == 1

def test_stale_state_and_source_block_confirmation(setup):
    library, runtime, _, doc = setup
    result = runtime.answer('2026-10-29', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    runtime.store.import_workspace('test', dict(SNAPSHOT, version=2, opening=100000))
    with pytest.raises(Conflict): runtime.workflows.confirm(result['proposal']['id'])
    fresh = runtime.answer('2026-10-29', order_id='TF-26104', document_id=doc, session_id=result['session_id'])
    lease = library.lease(doc,'test','test');library.revise(doc,'test',lease['token'],1,'new.txt',b'Payment changed.');library.process_next()
    with pytest.raises(Conflict): runtime.workflows.confirm(fresh['proposal']['id'])

def test_role_limits_order_scope_and_session_scope(setup):
    _, runtime, _, doc = setup
    result = runtime.answer('read email', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    with pytest.raises(Conflict): runtime.answer('read email', order_id='TF-26091', session_id=result['session_id'])
    run,_,_ = runtime.store.start('test', {'question':'test','order_id':'TF-26091'})
    with pytest.raises(ValueError): runtime.workflows.execute('wf_reconcile',run,'cash_flow',{})
    assert runtime.workflows.execute('wf_cash',run,'cash_flow',{})['status'] == 'needs_information'
    with pytest.raises(ValueError): runtime.workflows.execute('evidence_read',run,'reconciliation',{'document_id':doc})

def test_budget_failure_persists_and_allows_next_turn(setup, monkeypatch):
    _, runtime, _, doc = setup
    monkeypatch.setenv('TRADEX_AGENT_MAX_CALLS','1')
    result = runtime.answer('read email', document_id=doc, order_id='TF-26104', workspace=SNAPSHOT)
    assert result['task_status'] == 'failed'
    assert runtime.store.run(result['run_id'],'test')['trace'][-1]['event'] == 'failure'
    monkeypatch.setenv('TRADEX_AGENT_MAX_CALLS','18')
    result = runtime.answer('read email', document_id=doc, order_id='TF-26104', session_id=result['session_id'])
    assert result['task_status'] == 'needs_information'

def test_cash_matches_demo_and_does_not_double_count():
    full = cash(SNAPSHOT); partial = cash(dict(SNAPSHOT, amountUSD=6000))
    assert full['expected_net_cny'] == 80000 and partial['expected_net_cny'] == 40000
    assert partial['unscheduled_usd'] == 6000 and partial['peak_shortfall_cny'] == 34000
    assert len(partial['daily_balances']) == 56
    with pytest.raises(ValueError): cash(SNAPSHOT, delay=100)

@pytest.mark.parametrize('provider,key,base', [('openrouter','OPENROUTER_API_KEY','https://openrouter.ai/api/v1'),('qwen','DASHSCOPE_API_KEY','https://qwen.invalid/v1'),('deepseek','DEEPSEEK_API_KEY','https://api.deepseek.com')])
def test_provider_transport_parameters(provider,key,base,monkeypatch):
    monkeypatch.setenv('TRADEX_MODEL_PROVIDER',provider);monkeypatch.setenv(key,'fixture-only')
    monkeypatch.setenv('DASHSCOPE_BASE_URL','https://qwen.invalid/v1');monkeypatch.delenv('TRADEX_MODEL_BASE_URL',raising=False)
    monkeypatch.setenv('TRADEX_MODEL_CASH_FLOW','test-cash-model')
    monkeypatch.setenv('TRADEX_MODEL_MAX_TOKENS','4096')
    def respond(request):
        payload=json.loads(request.content)
        assert str(request.url)==base+'/chat/completions'
        assert payload['model']=='test-cash-model' and payload['tools']
        assert payload['max_tokens']==4096
        assert ('enable_thinking' in payload)==(provider=='qwen')
        if provider=='openrouter':
            assert payload['provider']['allow_fallbacks'] is False
            if payload['tools'][0].get('function', {}).get('name') == 'finish':
                assert payload['tool_choice'] == {'type':'function','function':{'name':'finish'}}
            else: assert payload['tool_choice'] == 'required'
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'{}'}}],'usage':{'total_tokens':10}})
    client=ModelClient(httpx.MockTransport(respond))
    _,usage=client.chat('cash_flow',[{'role':'user','content':'test'}],[{'type':'function'}])
    assert usage['usage']['total_tokens']==10
    client.chat('cash_flow',[{'role':'user','content':'finalize'}],[{'type':'function','function':{'name':'finish'}}])


def test_last_call_offers_only_finish(setup, monkeypatch):
    _, runtime, model, doc = setup
    monkeypatch.setenv('TRADEX_AGENT_MAX_CALLS', '1')
    seen = []
    def final(role, messages, tools):
        seen.extend(t['function']['name'] for t in tools)
        return {'role':'assistant','content':None,'tool_calls':[finish('needs_information')]}, {'usage':{}}
    model.chat = final
    result = runtime.answer('read email', document_id=doc, order_id='TF-26104', workspace=SNAPSHOT)
    assert seen == ['finish']
    assert result['task_status'] == 'needs_information'

def test_all_specialists_leave_a_call_for_coordinator_summary(setup, monkeypatch):
    _, runtime, model, _ = setup
    monkeypatch.setenv('TRADEX_AGENT_MAX_CALLS','18')
    calls=[]
    def many_steps(role,messages,tools):
        n=sum(m['role']=='assistant' for m in messages)
        calls.append(role)
        if role=='coordinator':
            if n==0: action=call('wf_status')
            elif n<=3: action=call('task',subagent_type=['reconciliation','cash_flow','decision'][n-1],description='Inspect current state')
            else: action=finish()
        elif [t['function']['name'] for t in tools]==['finish']: action=finish()
        else: action=call('wf_status')
        return {'role':'assistant','content':None,'tool_calls':[action]}, {'usage':{}}
    model.chat=many_steps
    result=runtime.answer('Analyze company cash',workspace=SNAPSHOT)
    assert result['task_status']=='completed'
    assert len(calls)==18 and calls[-1]=='coordinator'
    assert calls.count('decision')==3
    assert not any(e['event']=='failure' for e in result['trace'])

def test_failure_retains_completed_specialist_results(setup):
    _,runtime,model,_=setup
    def fail_after_specialist(role,messages,tools):
        n=sum(m['role']=='assistant' for m in messages)
        if role=='coordinator' and n: raise httpx.ReadTimeout('fixture')
        action=call('task',subagent_type='cash_flow',description='Analyze') if role=='coordinator' else finish()
        return {'role':'assistant','content':None,'tool_calls':[action]}, {'usage':{}}
    model.chat=fail_after_specialist
    result=runtime.answer('Analyze company cash',workspace=SNAPSHOT)
    assert result['task_status']=='failed' and result['failure_reason']=='model_connection'
    assert result['paragraphs'][0]['text']=='Evidence and financial analysis.'

@pytest.mark.parametrize('reason,message,usage', [
    ('output_truncated', {'content':None, 'tool_calls':[{'id':'cut','function':{'name':'finish','arguments':'{"status":"completed"'}}]}, {'finish_reason':'length'}),
    ('invalid_tool_arguments', {'content':None, 'tool_calls':[{'id':'bad','function':{'name':'finish','arguments':'not-json'}}]}, {'finish_reason':'tool_calls'}),
    ('missing_result', {'content':'Ordinary prose without a structured result.'}, {'finish_reason':'stop'}),
])
def test_model_output_failures_are_identified_without_retry(setup, reason, message, usage):
    _,runtime,model,_=setup
    calls=[]
    def broken(role,messages,tools):
        calls.append(role)
        return message, dict(usage,usage={'completion_tokens':1800})
    model.chat=broken
    result=runtime.answer('Analyze company cash',workspace=SNAPSHOT,language='en')
    assert result['task_status']=='failed'
    assert result['failure_reason']==reason
    assert calls==['coordinator']
    assert result['trace'][-1]['error_type']=='ModelOutputError'
    assert result['trace'][-1]['agent']=='coordinator'


def test_cash_agent_has_calculation_tools_without_unrelated_retrieval(setup):
    _,runtime,model,_=setup
    seen=[]
    def concise(role,messages,tools):
        n=sum(m['role']=='assistant' for m in messages)
        if role=='coordinator': action=call('task',subagent_type='cash_flow',description='Calculate cash') if n==0 else finish()
        else:
            seen.extend(t['function']['name'] for t in tools)
            action=call('wf_cash') if n==0 else finish()
        return {'content':None,'tool_calls':[action]}, {'usage':{}}
    model.chat=concise
    result=runtime.answer('Analyze company cash',workspace=SNAPSHOT)
    assert result['task_status']=='completed'
    assert 'wf_cash' in seen and not {'kb_search', 'sandbox_python'} & set(seen)


def test_current_tool_facts_replace_prior_model_prose(setup):
    _,runtime,model,_=setup
    first=runtime.answer('confirmed',workspace=SNAPSHOT)
    def inspect(role,messages,tools):
        context=json.loads(next(m['content'] for m in messages if m['role']=='user'))
        assert all('paragraphs' not in turn for turn in context['recent_turns'])
        assert all(set(source)<={'id','document_id','version','title','locator'} for source in context['known_sources'])
        n=sum(m['role']=='assistant' for m in messages)
        if n==0: action=call('task',subagent_type='cash_flow',description='Supplier extension only') if role=='coordinator' else call('wf_cash',supplier_extension_days=10)
        else:
            if role=='cash_flow':
                result=json.loads(next(m['content'] for m in messages if m['role']=='tool'))
                assert 'daily_balances' not in result
                assert result['supplier_payment_cny']==160000
                assert result['receipt_delay_days']==0
                assert result['supplier_extension_days']==10
                assert result['peak_shortfall_cny']==0
            action=finish()
        return {'content':None,'tool_calls':[action]}, {'usage':{}}
    model.chat=inspect
    result=runtime.answer('The supplier agrees to 10 extra days.',session_id=first['session_id'])
    assert result['task_status']=='completed'
