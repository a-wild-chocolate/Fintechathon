"""Real Deep Agents execution with a deterministic provider substitute."""
import json
import pytest
from test_agents import setup, SNAPSHOT, call, finish
from tradex_rag.agents.human import HumanAnswer
from tradex_rag.agents.runtime import AgentRuntime

QUESTION = {'question': 'Would you like a collection draft?', 'context': 'Choose the next action.',
            'options': ['Prepare a draft', 'Keep the current plan']}


def install_model(model, roles):
    calls = []
    def chat(role, messages, tools):
        context = json.loads(messages[1]['content'])
        resume = context.get('continuation')
        n = sum(m['role'] == 'assistant' for m in messages)
        calls.append(role)
        if role == 'coordinator':
            if resume:
                planned = set(roles) | set(resume['required_roles'])
                if 'reconciliation' in planned:
                    planned.update({'cash_flow','decision'} & resume['prior_specialist_results'].keys())
                if 'cash_flow' in planned and 'decision' in resume['prior_specialist_results']: planned.add('decision')
                ordered = [r for r in ('reconciliation','cash_flow','decision') if r in planned]
                if n == 0:
                    assert [t['function']['name'] for t in tools] == ['plan_resume']
                    action = call('plan_resume', rerun_roles=roles, decision_task='general',
                                  cash_scenarios=[{'receipt_delay_days': 3}] if 'cash_flow' in roles else [],
                                  response={'status':'completed','paragraphs':[{'text':'The current plan is unchanged.','sources':[]}]} if not ordered else None,
                                  reason='Apply the user clarification to affected tasks only.')
                elif n <= len(ordered): action = call('task', subagent_type=ordered[n-1], description='Continue with the supplied reply')
                else: action = finish()
            elif n < 3: action = call('task', subagent_type=['reconciliation','cash_flow','decision'][n], description='Analyze this case')
            else: action = call('finish', status='needs_information', paragraphs=[], questions=[QUESTION])
        elif role == 'reconciliation':
            action = call('evidence_read', document_id=model.doc_id) if n == 0 else finish(sources=[1])
        elif role == 'cash_flow': action = call('wf_cash') if n == 0 else finish()
        else: action = finish() if resume else call('finish',status='needs_information',paragraphs=[],questions=[QUESTION])
        return {'role':'assistant','tool_calls':[action]}, {'usage':{}}
    model.chat = chat
    return calls


def reply(runtime, result):
    answers = [HumanAnswer(question_id=q['id'], action='answer', option_index=1) for q in result['questions']]
    response, prepared = runtime.store.respond(result['run_id'],'test',answers,'en')
    return runtime.execute(*prepared)


@pytest.mark.parametrize('roles,expected_reuse', [
    (['decision'], {'reconciliation','cash_flow'}),
    (['cash_flow'], {'reconciliation'}),
    (['reconciliation'], set()),
    ([], {'reconciliation','cash_flow'}),
])
def test_reply_runs_only_affected_specialists(setup, roles, expected_reuse):
    _,runtime,model,doc = setup
    calls = install_model(model, roles)
    first = runtime.answer('Assess the order',language='en',order_id='TF-26104',document_id=doc,workspace=SNAPSHOT)
    assert first['task_status'] == 'needs_information'
    assert first['workflow_facts']['cash_flow'][0]['result']['peak_shortfall_cny'] == 32000
    calls.clear()
    result = reply(runtime, first)
    assert result['task_status'] == 'completed', result
    assert {e['agent'] for e in result['trace'] if e['event']=='agent_reused'} == expected_reuse
    assert not expected_reuse.intersection(calls)
    if roles == ['decision']: assert calls == ['coordinator','decision']
    if not roles: assert calls == ['coordinator']
    assert result['sources'][0]['document_id'] == doc
    if 'reconciliation' in expected_reuse: assert result['specialist_results']['reconciliation']['paragraphs'][0]['sources'] == [1]


def test_new_workspace_invalidates_cash_and_downstream_advice(setup):
    _,runtime,model,doc = setup
    calls=install_model(model,['decision'])
    first=runtime.answer('Assess the order',order_id='TF-26104',document_id=doc,workspace=SNAPSHOT)
    runtime.store.import_workspace('test',dict(SNAPSHOT,version=2,opening=100000))
    calls.clear()
    result=reply(runtime,first)
    assert result['task_status']=='completed'
    assert 'cash_flow' in calls and 'reconciliation' not in calls
    assert result['workflow_facts']['cash_flow'][0]['result']['opening_cny']==100000


def test_revised_evidence_is_not_reused(setup):
    library,runtime,model,doc=setup
    calls=install_model(model,['decision'])
    first=runtime.answer('Assess the order',order_id='TF-26104',document_id=doc,workspace=SNAPSHOT)
    lease=library.lease(doc,'test','test')
    library.revise(doc,'test',lease['token'],1,'updated.txt',b'The payment conditions changed.')
    library.process_next()
    calls.clear()
    result=reply(runtime,first)
    assert result['task_status']=='completed'
    assert {'reconciliation','cash_flow','decision'} <= set(calls)
    assert not any(e['event']=='agent_reused' for e in result['trace'])


def test_saved_specialists_survive_runtime_restart(setup):
    library,runtime,model,doc=setup
    calls=install_model(model,['decision'])
    first=runtime.answer('Assess the order',order_id='TF-26104',document_id=doc,workspace=SNAPSHOT)
    restarted=AgentRuntime(library,model=model,connector=runtime.connector)
    calls.clear()
    result=reply(restarted,first)
    assert result['task_status']=='completed'
    assert 'cash_flow' not in calls and 'reconciliation' not in calls


def test_completed_calculation_survives_an_unanswered_preference(setup):
    from tradex_rag.agents.runtime import Turn
    from tradex_rag.agents.continuation import Continuation
    _, runtime, model, doc = setup
    install_model(model, ['decision'])
    first = runtime.answer('Assess the order', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    parent = runtime.store.run(first['run_id'], 'test')
    parent['result']['specialist_results']['cash_flow']['status'] = 'needs_information'
    run, _, request, history = runtime.prepare('Keep dates; draft collection', order_id='TF-26104', document_id=doc)
    turn = Turn(runtime, run, request, history)
    continuation = Continuation(turn, parent)
    plan = continuation.plan(['cash_flow', 'decision'], 'Owner selected a collection draft.')
    assert plan['rerun_roles'] == ['decision']
    assert 'cash_flow' not in turn.outputs  # Do not promote unfinished model prose.
    assert turn.facts['cash_flow'][0]['result']['peak_shortfall_cny'] == 32000
    assert 'paragraphs' not in continuation.context()['prior_specialist_results']['cash_flow']
    assert any(e['event'] == 'workflow_reused' for e in runtime.store.run(run, 'test')['trace'])


def test_saved_web_citation_is_not_a_local_document(setup):
    from tradex_rag.agents.runtime import Turn
    from tradex_rag.agents.continuation import Continuation
    _, runtime, model, doc = setup
    install_model(model, ['decision'])
    first = runtime.answer('Assess the order', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    parent = runtime.store.run(first['run_id'], 'test')
    parent['result']['sources'].append({'id':2,'document_id':'web-example','kind':'web','version':1})
    parent['result']['specialist_results']['decision']['paragraphs'] = [{'text':'Public context','sources':[2]}]
    run, _, request, history = runtime.prepare('Keep the current plan', order_id='TF-26104')
    continuation = Continuation(Turn(runtime, run, request, history), parent)
    assert continuation.changed_sources == []


def test_approval_status_requires_an_actual_pending_proposal(setup):
    _, runtime, model, _ = setup
    model.chat = lambda *args: ({'role':'assistant', 'tool_calls':[finish('needs_approval')]}, {'usage':{}})
    result = runtime.answer('Prepare a collection draft', language='en', workspace=SNAPSHOT)
    assert result['proposal'] is None
    assert result['task_status'] == 'completed'


def test_workspace_change_invalidates_calculations_without_a_saved_agent_result(setup):
    from tradex_rag.agents.runtime import Turn
    from tradex_rag.agents.continuation import Continuation
    _, runtime, model, doc = setup
    install_model(model, ['decision'])
    first = runtime.answer('Assess the order', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    parent = runtime.store.run(first['run_id'], 'test')
    parent['result']['specialist_results'].pop('cash_flow')
    runtime.store.import_workspace('test', dict(SNAPSHOT, version=2, opening=100000))
    run, _, request, history = runtime.prepare('Draft collection', order_id='TF-26104')
    continuation = Continuation(Turn(runtime, run, request, history), parent)
    assert continuation.cash_facts == []
    assert continuation.plan(['decision'], 'Prepare a draft')['rerun_roles'] == ['cash_flow','decision']


@pytest.mark.parametrize("duplicate", [False, True])
def test_decision_saves_draft_and_finishes_in_one_model_call(setup, duplicate):
    _, runtime, model, doc = setup
    install_model(model, ['decision'])
    first = runtime.answer('Assess the order', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    calls = []
    def chat(role, messages, tools):
        calls.append(role)
        if role == 'coordinator':
            action = call('plan_resume', rerun_roles=['decision'], decision_task='draft', reason='Prepare the selected collection draft.')
        else:
            assert [t['function']['name'] for t in tools] == ['finish']
            action = call('finish', status='completed', paragraphs=[{'text':'Your draft is ready; the CNY 32,000 gap is unchanged.','sources':[]}],
                          draft={'kind':'collection','text':'Could you confirm payment before 22 October?'})
        actions = [action, dict(action, id=action['id']+'-duplicate')] if duplicate else [action]
        return {'role':'assistant','tool_calls':actions}, {'usage':{}}
    model.chat = chat
    result = reply(runtime, first)
    assert result['task_status'] == 'completed', result
    assert calls == ['coordinator', 'decision']
    drafts = [e for e in result['trace'] if e['event']=='tool_result' and e.get('tool')=='wf_draft']
    assert len(drafts) == 1 and drafts[0]['result']['status']=='draft'
    assert result['workspace']['version']==1


def test_repeated_cash_tool_is_cached_until_workspace_changes(setup):
    import asyncio
    from tradex_rag.agents.runtime import Turn
    from tradex_rag.agents.harness import workflow_tool
    _, runtime, _, doc = setup
    run, _, request, history = runtime.prepare('Calculate cash', order_id='TF-26104', workspace=SNAPSHOT)
    turn = Turn(runtime, run, request, history)
    calls = []
    class Client:
        async def call(self, role, name, arguments):
            calls.append(name)
            return runtime.workflows.execute(name,run,role,arguments)
    turn.client = Client()
    tool = workflow_tool(turn,'cash_flow',{'function':{'name':'wf_cash','parameters':{'type':'object','properties':{}}}})
    async def check():
        first = await tool.ainvoke({})
        assert await tool.ainvoke({}) == first
        runtime.store.import_workspace('test',dict(SNAPSHOT,version=2,opening=100000))
        assert (await tool.ainvoke({}))['opening_cny']==100000
    asyncio.run(check())
    assert calls==['wf_cash','wf_cash']
