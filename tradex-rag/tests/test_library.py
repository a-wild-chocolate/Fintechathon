import json,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tradex_rag.config import Settings
from tradex_rag.service import Library,Conflict,NotFound,AccessDenied
from tradex_rag.parsing import parse,chunk,lexical_tokens
from tradex_rag.api import create_app

class TestEmbedding:
    __test__=False
    dimensions=4;model_id='test-concepts';collection='test_concepts'
    def documents(self,texts):
        return [[1+int('付款' in t or 'payment' in t),1+int('税' in t or 'tax' in t),1+int('原产' in t),1] for t in texts]
    def query(self,text):return self.documents([text])[0]

@pytest.fixture
def lib(tmp_path):
    l=Library(Settings(data_dir=tmp_path),embedding=TestEmbedding());yield l;l.close()
def add(lib,text='付款金额尚未确定，客户会确认日期。',tenant='a',metadata=None):
    r=lib.create('email.txt',text.encode(),'客户邮件',tenant,metadata)
    lib.process_next();return r

def test_persistent_real_qdrant_storage(lib):
    r=add(lib);s=lib.search('付款日期','a',mode='vector')
    assert s['results'][0]['document_id']==r['document_id']
    assert s['results'][0]['citation']['locator']=='paragraph 1'
    assert s['semantic_available'] and (lib.root/'qdrant').exists()

def test_tenant_and_public_scope(lib):
    add(lib,'secret-a 付款',tenant='a');add(lib,'secret-b 付款',tenant='b');pub=add(lib,'公共政策 付款',tenant='public')
    for mode in ['keyword','vector','hybrid']:
        r=lib.search('付款','a',mode=mode)
        assert r['results'] and all('secret-b' not in h['context'] for h in r['results'])
    with pytest.raises(AccessDenied):lib.lease(pub['document_id'],'a','agent')

def test_filtered_before_top_k(lib):
    own=add(lib,'特殊付款','a')
    for i in range(8):add(lib,'特殊付款 特殊付款 特殊付款','b')
    assert lib.search('特殊付款','a',limit=1)['results'][0]['document_id']==own['document_id']

def test_one_writer_and_version_history(lib):
    r=add(lib);doc=r['document_id'];lease=lib.lease(doc,'a','first')
    with pytest.raises(Conflict):lib.lease(doc,'a','second')
    saved=lib.revise(doc,'a',lease['token'],1,'email.txt','确认付款为6000美元，预计10月29日。'.encode())
    assert saved['version']==2
    assert lib.document(doc,'a')['current_version']==1
    lib.process_next()
    assert lib.document(doc,'a')['current_version']==2
    assert Path(lib.original(doc,1,'a')['path']).read_text()=='付款金额尚未确定，客户会确认日期。'
    assert all(h['version']==2 for h in lib.search('付款','a')['results'])
    with pytest.raises(Conflict):lib.revise(doc,'a',lease['token'],1,'email.txt',b'stale')

def test_expired_holder_cannot_commit(lib):
    now=[1000.0];lib.clock=lambda:now[0];doc=add(lib)['document_id'];old=lib.lease(doc,'a','old',2)
    now[0]+=3;new=lib.lease(doc,'a','new',60)
    assert new['fence']>old['fence']
    with pytest.raises(Conflict):lib.revise(doc,'a',old['token'],1,'x.txt',b'old')
    lib.revise(doc,'a',new['token'],1,'x.txt',b'new')

def test_simultaneous_lease_requests(lib):
    doc=add(lib)['document_id']
    def attempt(owner):
        try:return lib.lease(doc,'a',owner)['token']
        except Conflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,['agent-1','agent-2']))
    assert sum(r is not None for r in results)==1

def test_failed_embeddings_keep_keyword_evidence(lib):
    def fail(texts):raise RuntimeError('provider unavailable')
    lib.embedding.documents=fail;r=add(lib)
    assert lib.jobs('a')[0]['status']=='embedding_failed'
    assert lib.search('付款','a')['results']
    assert not lib.search('付款','a')['semantic_available']
    lib.embedding.documents=TestEmbedding().documents
    lib.retry(r['job_id'],'a');lib.process_next()
    assert lib.stats('a')['embedded_chunks']>0

def test_archive_hides_results_and_original(lib):
    r=add(lib);lib.delete(r['document_id'],'a')
    assert not lib.search('付款','a')['results']
    with pytest.raises(NotFound):lib.original(r['document_id'],1,'a')

def test_policy_status_market_and_dates(lib):
    add(lib,'税款 过期',tenant='public',metadata={'effective_to':'2020-01-01'})
    add(lib,'税款 提案',tenant='public',metadata={'allowed_use':'monitoring_only'})
    add(lib,'税款 欧洲',tenant='public',metadata={'jurisdiction':'EU'})
    add(lib,'税款 英国',tenant='public',metadata={'jurisdiction':'GB'})
    r=lib.search('税款','a',market='GB',as_of='2026-10-18')
    assert len(r['results'])==1 and '英国' in r['results'][0]['context']

def test_events_replayable_and_no_financial_side_effect(lib):
    r=add(lib);events=lib.events('a');kinds=[e['kind'] for e in events]
    assert kinds==['document.uploaded','document.parsed','document.ready']
    assert lib.events('b')==[]
    assert lib.events('a',events[-1]['id'])==[]

def test_chunk_boundaries_and_evidence_locations():
    blocks=[{'text':'付款条件。'*400,'section':'第1条','locator':'page 1'},{'text':'HS: 9405 | amount: 6000','section':'Table','locator':'row 2'}]
    parents,children=chunk(blocks)
    assert len(children)>2
    assert all(c['parent_id'] in {p['id'] for p in parents} for c in children)
    assert any(c['text']=='HS: 9405 | amount: 6000' and c['locator']=='row 2' for c in children)
    assert '付款' in lexical_tokens('客户付款日期')

def test_csv_and_eml(tmp_path):
    p=tmp_path/'trade.csv';p.write_text('invoice,amount\nA-1,6000\nB-2,4000\n')
    b=parse(p);assert len(b)==2 and 'amount: 6000' in b[0]['text']
    p=tmp_path/'mail.eml';p.write_text('From: a@example.com\nSubject: payment\nContent-Type: text/plain; charset=utf-8\n\nAmount pending.\n')
    assert any('Amount pending' in b['text'] for b in parse(p))

def test_api_async_upload_and_lock(tmp_path):
    settings=Settings(data_dir=tmp_path,tenant='test-api');library=Library(settings,embedding=TestEmbedding())
    with TestClient(create_app(settings,library)) as client:
        r=client.post('/api/uploads',files={'file':('mail.txt','付款金额缺失'.encode(),'text/plain')},data={'order_id':'TF-26104'})
        assert r.status_code==202;doc=r.json()['document_id']
        for _ in range(100):
            if client.get('/api/documents/'+doc).json()['current_version']==1:break
            time.sleep(.02)
        r=client.post('/api/search',json={'query':'付款'})
        assert r.status_code==200 and r.json()['results']
        lease=client.post(f'/api/documents/{doc}/lease',json={});assert lease.status_code==200
        assert client.post(f'/api/documents/{doc}/lease',json={}).status_code==409
        assert client.get(f'/api/documents/{doc}/versions/1/original').content=='付款金额缺失'.encode()
