import pytest
from fastapi.testclient import TestClient
from tradex_rag.api import create_app
from tradex_rag.config import Settings
from tradex_rag.service import Library
from tradex_rag.agents.store import AgentStore
from tradex_rag.agents.workflows import Workflows
from tradex_rag.business_records import CompanyInput, OrderInput
from test_library import TestEmbedding

COMPANY={'name':'Pearl Export Co','country':'CN','planning_start':'2026-11-01','opening_cny':50000,'opening_usd':2000}
ORDER={'id':'PE-901','version':1,'customer':'New Buyer','country':'DE','goods':'Outdoor lights','currency':'EUR','total':10000,'received':2000,'expected':5000,'receipt_date':'2026-11-15','fx_rate':8,'supplier':'New Supplier','supplier_amount':70000,'supplier_date':'2026-11-05','status':'preparing'}

@pytest.fixture
def client(tmp_path):
    settings=Settings(data_dir=tmp_path,tenant='local')
    library=Library(settings,embedding=TestEmbedding())
    with TestClient(create_app(settings,library)) as c: yield c

def test_preview_commit_edit_and_isolation(client):
    a=client.post('/api/companies',json=COMPANY).json();b=client.post('/api/companies',json=dict(COMPANY,name='Second')).json()
    base='/api/companies/'+a['company']['id'];other='/api/companies/'+b['company']['id']
    assert a['snapshot']['orders']==[] and a['snapshot']['movements']==[]
    preview=client.post(base+'/business/orders/preview',json=ORDER)
    assert preview.status_code==200,preview.text
    assert preview.json()['after']['peak_shortfall_cny']==20000
    assert client.get(base+'/business/overview').json()['snapshot']['orders']==[]
    saved=client.post(base+'/business/orders',json=ORDER)
    assert saved.status_code==201,saved.text
    saved=saved.json();assert saved['snapshot']['version']==2
    assert saved['snapshot']['orders'][0]['currency']=='EUR'
    assert saved['cash']['unscheduled_balances'][0]['amount']==3000
    assert client.get(other+'/business/overview').json()['snapshot']['orders']==[]
    assert client.get('/api/companies/missing/business/overview').status_code==404
    assert client.post(base+'/business/orders',json=dict(ORDER,version=2)).status_code==409
    edited=client.put(base+'/business/orders/PE-901',json=dict(ORDER,version=2,supplier_amount=30000)).json()
    assert edited['cash']['peak_shortfall_cny']==0 and len(edited['snapshot']['movements'])==2
    assert client.put(base+'/business/orders/PE-901',json=dict(ORDER,version=2)).status_code==409
    assert client.post(base+'/business/orders',json=dict(ORDER,id='INVALID',version=3,expected=9000)).status_code==422
    assert client.get(base+'/agents/workspace').json()['workspace']['orders'][0]['supplier_amount']==30000

def test_cancel_keeps_order_and_removes_future_movements(client):
    a=client.post('/api/companies',json=COMPANY).json();base='/api/companies/'+a['company']['id']
    client.post(base+'/business/orders',json=ORDER)
    result=client.put(base+'/business/orders/PE-901',json=dict(ORDER,version=2,status='cancelled')).json()
    assert result['snapshot']['orders'][0]['status']=='cancelled'
    assert result['snapshot']['movements']==[] and result['cash']['peak_shortfall_cny']==0

def test_generic_agent_tools_and_confirmation(tmp_path):
    settings=Settings(data_dir=tmp_path,tenant='local');lib=Library(settings,embedding=TestEmbedding())
    store=AgentStore(tmp_path/'agents.sqlite3');company=store.business.create_company('local',CompanyInput(**COMPANY))['company']['id']
    store.business.save_order(company,OrderInput(**ORDER),create=True)
    from copy import copy
    from dataclasses import replace
    scoped=copy(lib);scoped.settings=replace(settings,tenant=company)
    tools=Workflows(scoped,store)
    run,session,_=store.start(company,{'question':'Partial payment','order_id':'PE-901','language':'en'})
    assert tools.execute('wf_status',run,'coordinator',{})['workspace']['company_name']=='Pearl Export Co'
    assert tools.execute('wf_cash',run,'cash_flow',{})['first_shortfall']['date']=='2026-11-05'
    proposal=tools.execute('wf_reconcile',run,'reconciliation',{'amount':3000,'currency':'EUR','receipt_date':'2026-11-10'})
    confirmed=tools.confirm(proposal['id'])
    assert confirmed['workspace']['orders'][0]['expected']==3000
    assert confirmed['workspace']['opening']==50000
    assert confirmed['workspace']['orders'][0]['received']==2000
    assert confirmed['after']['unscheduled_balances'][0]['amount']==5000
    assert tools.confirm(proposal['id'])==confirmed
    assert store.business.overview(company)['snapshot']['version']==3
    lib.close()

def test_model_values_are_major_currency_units():
    from tradex_rag.business_records import for_model
    value=for_model({'accounts':[{'currency':'CNY','opening_minor':5000000}],
                     'movements':[{'currency':'CNY','signed_minor':4000000,'original_minor':500000,'original_currency':'EUR'}]})
    assert value['accounts'][0]['opening_balance']==50000
    assert value['movements'][0]['amount']==40000
    assert value['movements'][0]['original_amount']==5000
    assert '_minor' not in str(value)

def test_clarification_uses_the_saved_order_currency():
    from tradex_rag.agents.human import question_cards
    cards=question_cards({}, {'currency':'EUR','missing_fields':['amount','receipt_date']}, 'en', {})
    assert 'EUR' in cards[0]['question'] and 'USD' not in cards[0]['question']

def test_edit_preserves_recorded_adjustments(client):
    company=client.post('/api/companies',json=COMPANY).json()['company']['id']
    base='/api/companies/'+company
    client.post(base+'/business/orders',json=ORDER)
    with client.app.state.agents.store.db.connect(write=True) as db:
        db.execute('UPDATE trade_orders SET adjustment_minor=3000 WHERE company_id=?',(company,))
    changed=client.put(base+'/business/orders/PE-901',json=dict(ORDER,version=2,supplier_amount=30000))
    assert changed.status_code==200,changed.text
    assert changed.json()['snapshot']['orders'][0]['adjustment']==30
    invalid=client.put(base+'/business/orders/PE-901',json=dict(ORDER,version=3,expected=8000))
    assert invalid.status_code==400

def test_scoped_runs_documents_and_mcp_tool_routing(client):
    a=client.post('/api/companies',json=COMPANY).json()['company']['id']
    b=client.post('/api/companies',json=dict(COMPANY,name='Other')).json()['company']['id']
    base='/api/companies/'+a;other='/api/companies/'+b
    client.post(base+'/business/orders',json=ORDER)
    run,_,_=client.app.state.agents.store.start(a,{'question':'Check cash','order_id':'PE-901','language':'en'})
    result=client.post('/api/agent-tools/wf_status',json={'run_id':run,'role':'coordinator','arguments':{}})
    assert result.status_code==200,result.text
    assert result.json()['workspace']['accounts'][0]['opening_balance']==50000
    assert client.get(other+'/agents/runs/'+run).status_code in (403,404)
    cash=client.post('/api/agent-tools/wf_cash',json={'run_id':run,'role':'cash_flow','arguments':{}}).json()
    receipt=next(m for m in cash['movements'] if m['amount']>0)
    assert receipt['amount']==40000 and receipt['original_amount']==5000
    doc=client.post(base+'/text-uploads',json={'filename':'buyer.txt','title':'Buyer','text':'Expected payment date pending.','order_id':'PE-901'}).json()
    assert client.get(other+'/documents/'+doc['document_id']).status_code in (403,404)
    assert client.get(base+'/documents/'+doc['document_id']).status_code==200


def test_reconciliation_tool_requires_explicit_payment_fields():
    from types import SimpleNamespace
    from tradex_rag.agents.mcp_client import WorkflowClient
    tool = SimpleNamespace(name='wf_reconcile', description='Receipt', input_schema={
        'type':'object', 'properties':{k:{} for k in ('run_id','role','amount_usd','amount','currency','receipt_date','evidence_ids')},
        'required':['run_id','role']})
    schema = WorkflowClient(None, [tool], 'run').definitions('reconciliation')[0]['function']['parameters']
    assert set(schema['required']) == {'amount','currency','receipt_date','evidence_ids'}
    assert 'amount_usd' not in schema['properties']
    assert 'YYYY-MM-DD' in schema['properties']['receipt_date']['description']


def test_partial_receipt_timing_does_not_erase_amount_gap():
    from tradex_rag.business_records import forecast
    snapshot={'version':3,'planning_start':'2026-11-01','opening':42000,
              'orders':[{'id':'CW-GB-112','currency':'GBP','total':18000,'received':3000,'adjustment':0,'expected':4000,'status':'preparing'}],
              'movements':[{'order_id':'CW-GB-112','due_date':'2026-11-16','currency':'CNY','signed_minor':3680000,'status':'expected'},
                           {'order_id':'CW-GB-112','due_date':'2026-11-09','currency':'CNY','signed_minor':-9500000,'status':'obligation'}]}
    assert forecast(snapshot)['peak_shortfall_cny']==53000
    assert forecast(snapshot,'CW-GB-112',delay=-10)['peak_shortfall_cny']==16200
    assert forecast(snapshot,'CW-GB-112',extension=8)['peak_shortfall_cny']==16200
    assert forecast(snapshot)['unscheduled_balances'][0]['amount']==11000
