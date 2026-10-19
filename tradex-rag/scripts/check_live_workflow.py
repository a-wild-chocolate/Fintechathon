import json,time
from pathlib import Path
import httpx
client=httpx.Client(base_url='http://127.0.0.1:8765',timeout=30)
def ready(doc,version):
    for _ in range(100):
        d=client.get('/api/documents/'+doc).json()
        if d['current_version']==version and d['versions'][0]['status']=='ready':return d
        time.sleep(.1)
    raise AssertionError('Indexing did not complete')
r=client.post('/api/text-uploads',json={'filename':'agent-draft.md','title':'TF-26104 Agent协作草稿（模拟）','text':'# 内部协作草稿\n\n建议与供应商讨论付款延期，尚未取得供应商同意。','order_id':'TF-26104'});r.raise_for_status();doc=r.json()['document_id']
ready(doc,1)
lease=client.post(f'/api/documents/{doc}/lease',json={'seconds':120}).json()
conflict=client.post(f'/api/documents/{doc}/lease',json={});assert conflict.status_code==409
original=client.get(f'/api/documents/{doc}/versions/1/original').content
r=client.post(f'/api/documents/{doc}/versions',json={'token':lease['token'],'base_version':lease['base_version'],'filename':'agent-draft.md','text':'# 内部协作草稿\n\n建议与供应商讨论付款延期，尚未取得供应商同意。\n\n下一步：询问客户预计部分付款的金额和日期；收到书面回复后再调整现金流情景。'});r.raise_for_status()
ready(doc,2)
assert client.get(f'/api/documents/{doc}/versions/1/original').content==original
r=client.post('/api/search',json={'query':'部分付款金额日期','document_id':doc});r.raise_for_status();result=r.json();assert result['results'] and all(h['version']==2 for h in result['results'])
all_events=[];cursor=0
while True:
    page=client.get('/api/events',params={'after':cursor}).json()
    if not page:break
    all_events.extend(page);cursor=page[-1]['id']
events=[e['kind'] for e in all_events if e['document_id']==doc]
report={'document_id':doc,'upload_and_async_index':True,'concurrent_writer_rejected':True,'revision_2_searchable':True,'revision_1_original_preserved':True,'real_vector_search':result['semantic_available'],'test_document':'synthetic internal draft, not a customer contract','persisted_events':events}
Path('docs/live_workflow_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
