import json
import pytest
from tradex_rag.agents.store import AgentStore
from tradex_rag.agents.workflows import cash
from tradex_rag.service import Conflict

SNAPSHOT={'version':1,'opening':128000,'supplierDay':5,'receiptDay':12,'amountUSD':12000}

def payload():
    return {'state':{'lang':'en','context':'company','followups':{'read':['one']}},'docGroup':'receipts','docUploads':{},
            'flow':{'version':1,'opening':128000,'supplierDay':5,'receiptDay':12,'jobs':[],'chat':[{'id':'turn-1','question':'Example'}],'setup':None}}

def test_relational_records_and_fresh_store_restore(tmp_path):
    path=tmp_path/'agents.sqlite3'; store=AgentStore(path)
    saved=store.business.save_view('firm-a','main',0,payload())
    assert saved['revision']==1
    fresh=AgentStore(path)
    records=fresh.business.records('firm-a')
    assert records['company']['name']=='StarSail Exports'
    assert len(records['trade_orders'])==2
    assert len(records['bank_accounts'])==2
    assert len(records['cash_movements'])==6
    assert records['bank_accounts'][0]['opening_minor']==12800000
    view=fresh.business.view('firm-a','main')
    assert view['workspace']['flow']['opening']==128000
    assert view['workspace']['flow']['chat'][0]['id']=='turn-1'
    assert view['workspace']['state']['followups']['read']==['one']
    assert cash(fresh.workspace('firm-a'))['peak_shortfall_cny']==32000
    assert fresh.business.records('firm-b')['trade_orders']==[]

def test_old_browser_cannot_overwrite_confirmed_finances_or_another_browser(tmp_path):
    store=AgentStore(tmp_path/'db.sqlite3'); store.business.save_view('a','main',0,payload())
    store.import_workspace('a',dict(SNAPSHOT,version=2,amountUSD=6000))
    result=store.business.save_view('a','main',1,payload())
    assert result['workspace']['flow']['partialReceipt']['amountUSD']==6000
    assert result['workspace']['flow']['opening']==128000
    with pytest.raises(Conflict): store.business.save_view('a','main',1,payload())
    assert cash(store.workspace('a'))['peak_shortfall_cny']==34000
    order=next(x for x in store.business.records('a')['trade_orders'] if x['id']=='TF-26104')
    assert order['total_minor']-order['received_minor']==1200000

def test_migration_is_idempotent_and_preserves_original_snapshot(tmp_path):
    store=AgentStore(tmp_path/'db.sqlite3')
    with store.db.connect(write=True) as db:
        db.execute('INSERT INTO agent_workspaces VALUES(?,?,?)',('legacy',4,json.dumps(dict(SNAPSHOT,version=4,amountUSD=6000))))
    migrated=AgentStore(tmp_path/'db.sqlite3'); again=AgentStore(tmp_path/'db.sqlite3')
    assert migrated.workspace('legacy')==again.workspace('legacy')
    with again.db.connect() as db:
        assert db.execute('SELECT count(*) FROM financial_revisions').fetchone()[0]==1
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]

def test_unfinished_setup_does_not_create_orders_or_cash(tmp_path):
    store=AgentStore(tmp_path/'db.sqlite3'); data=payload()
    data['flow']['setup']={'records':{},'complete':False};data['flow']['opening']=0
    result=store.business.save_view('new','session',0,data)
    assert result['financial'] is None
    assert store.business.records('new')['trade_orders']==[]
    assert result['workspace']['flow']['setup']['complete'] is False

def test_failed_version_write_rolls_back_view_and_finances(tmp_path):
    store=AgentStore(tmp_path/'db.sqlite3');store.business.save_view('a','main',0,payload())
    data=payload();data['flow']['opening']=1000
    with pytest.raises(Conflict): store.business.save_view('a','main',1,data)
    assert store.business.view('a','main')['revision']==1
    assert store.workspace('a')['opening']==128000

def test_api_restores_business_and_view_after_restart(tmp_path):
    from fastapi.testclient import TestClient
    from tradex_rag.api import create_app
    from tradex_rag.config import Settings
    from tradex_rag.service import Library
    from test_library import TestEmbedding
    settings=Settings(data_dir=tmp_path,tenant='api-firm')
    for first in (True,False):
        library=Library(settings,embedding=TestEmbedding())
        with TestClient(create_app(settings,library)) as client:
            if first:
                response=client.put('/api/business/workspace',json={'revision':0,'workspace':payload()})
                assert response.status_code==200, response.text
                assert client.put('/api/business/workspace',json={'revision':0,'workspace':payload()}).status_code==409
            view=client.get('/api/business/workspace').json()
            assert view['workspace']['flow']['opening']==128000
            assert view['workspace']['flow']['chat'][0]['id']=='turn-1'
            assert view['business']['company']['name']=='StarSail Exports'
            records=client.get('/api/business').json()
            assert len(records['trade_orders'])==2
            assert records['cash_movements'][0]['company_id']=='api-firm'
