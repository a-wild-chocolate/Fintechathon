import pytest
from test_agents import setup, SNAPSHOT, call, finish
from tradex_rag.agents.human import HumanAnswer
from tradex_rag.agents.store import AgentStore
from tradex_rag.service import Conflict, NotFound


def test_structured_reply_is_persisted_and_resumes_only_once(setup):
    library, runtime, _, doc = setup
    first = runtime.answer('read email', language='en', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    questions = first['questions']
    assert len(questions) == 2 and all(len(q['options']) == 2 for q in questions)
    answers = [HumanAnswer(question_id=q['id'], action='answer', option_index=0, comment='6000')
               if q['field'] == 'amount_usd' else HumanAnswer(question_id=q['id'], action='skip') for q in questions]
    response, prepared = runtime.store.respond(first['run_id'], 'test', answers, 'en')
    restored = AgentStore(library.root / 'agents.sqlite3')
    repeated, duplicate = restored.respond(first['run_id'], 'test', answers, 'en')
    assert repeated == response and duplicate is None
    request = restored.run(response['run_id'], 'test')['request']
    assert request['reply_to_run_id'] == first['run_id'] and request['human_answers'][0]['comment'] == '6000'
    result = runtime.execute(*prepared)
    assert result['session_id'] == first['session_id']
    assert result['proposal']['amount_usd'] == 6000 and result['proposal']['receipt_date'] is None
    assert result['questions'] == []  # The skipped date is not immediately asked again.
    assert runtime.store.workspace('test')['version'] == 1
    assert runtime.store.workspace('test')['amountUSD'] == 12000


def test_choices_are_agent_generated_and_unknown_answers_do_not_change_cash(setup):
    _, runtime, model, _ = setup
    def clarify(role, messages, tools):
        return {'role':'assistant','tool_calls':[call('finish',status='needs_information',paragraphs=[],questions=[
            {'question':'Which payment is delayed?', 'context':'The cash effects differ.',
             'options':['The buyer paying us', 'Our payment to the supplier']}
        ])]}, {'usage':{}}
    model.chat = clarify
    first = runtime.answer('Payment will be delayed', language='en', workspace=SNAPSHOT)
    q = first['questions'][0]
    assert q['options'][1] == 'Our payment to the supplier'
    answers = [HumanAnswer(question_id=q['id'], action='skip', comment='I will check tomorrow.')]
    response, prepared = runtime.store.respond(first['run_id'],'test',answers,'en')
    result = runtime.execute(*prepared)
    assert result['questions'] == []
    assert runtime.store.workspace('test')['version'] == 1
    assert response['answers'][0]['selected_option'] is None


def test_clarification_validation_and_stale_questions(setup):
    _, runtime, _, doc = setup
    first = runtime.answer('read email', order_id='TF-26104', document_id=doc, workspace=SNAPSHOT)
    answers = [HumanAnswer(question_id=q['id'], action='skip') for q in first['questions']]
    with pytest.raises(NotFound): runtime.store.respond(first['run_id'],'other-tenant',answers,'zh')
    with pytest.raises(ValueError): runtime.store.respond(first['run_id'],'test',answers[:1],'zh')
    bad = [answers[0].model_copy(update={'action':'answer','option_index':3}), answers[1]]
    with pytest.raises(ValueError): runtime.store.respond(first['run_id'],'test',bad,'zh')
    bad = [answers[0].model_copy(update={'action':'answer'}), answers[1]]
    with pytest.raises(ValueError): runtime.store.respond(first['run_id'],'test',bad,'zh')
    runtime.answer('6000',order_id='TF-26104',document_id=doc,session_id=first['session_id'])
    with pytest.raises(Conflict): runtime.store.respond(first['run_id'],'test',answers,'zh')
