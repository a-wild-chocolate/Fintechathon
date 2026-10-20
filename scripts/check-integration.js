// Runs against the local frontend proxy and RAG service; no model API calls.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const base = process.env.TRADEX_FRONTEND_URL || 'http://127.0.0.1:5173';
async function api(path, options = {}) {
  const r = await fetch(base + '/api' + path, options);
  const data = await r.json();
  assert.ok(r.ok, JSON.stringify(data));
  return data;
}
const json = body => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
assert.equal((await api('/assistant/status')).mode, 'evidence', 'Run integration checks with TRADEX_AGENTS_ENABLED=0 and TRADEX_CHAT_ENABLED=0 to avoid paid inference.');
const text = await readFile(new URL('../tests/fixtures/payment-confirmation.txt', import.meta.url), 'utf8');
const form = new FormData();
form.append('file', new Blob([text], {type:'text/plain'}), 'integration-check.txt');
form.append('title', '[Integration test] Payment evidence');
form.append('order_id', 'TF-26104');
const doc = await api('/uploads', {method:'POST',body:form});
try {
  let ready;
  for (let n=0;n<100;n++) {
    ready = await api('/documents/'+doc.document_id);
    if (ready.versions[0].status === 'ready') break;
    if (['failed','embedding_failed'].includes(ready.versions[0].status)) throw Error('Indexing failed');
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  assert.equal(ready.versions[0].status,'ready');
  for (const [language,question] of [['en','What is the partial payment amount and date?'],['zh','客户付款金额、日期和余款安排是什么？']]) {
    const answer = await api('/assistant/chat',json({question,language,document_id:doc.document_id,order_id:'TF-26104'}));
    assert.equal(answer.mode,'evidence');
    assert.ok(answer.sources.length);
    assert.ok(answer.paragraphs.some(p=>p.text.includes('6,000')));
    assert.ok(answer.sources.every(s=>s.document_id===doc.document_id && s.version===1));
    const source = answer.sources[0];
    const original = await fetch(base+source.original_url);
    assert.equal(await original.text(),text);
    const version = await api(`/documents/${doc.document_id}/versions/1`);
    assert.equal(version.selected_version,1);
    assert.ok(version.content.length);
  }
  const wrongOrder=await fetch(base+'/api/assistant/chat',json({question:'payment',document_id:doc.document_id,order_id:'TF-26091'}));
  assert.equal(wrongOrder.status,400);
  const policies=(await api('/documents')).filter(d=>d.tenant==='public');
  assert.ok(policies.length > 0, 'No public policies found. Run backend seed and drain before this check.');
  assert.ok(policies.every(d=>d.metadata.title_en));
  console.log('PASS: proxy, upload, async indexing, Chinese/English retrieval, citations, original version, order scope, English policy titles.');
} finally {
  await api('/documents/'+doc.document_id,{method:'DELETE'});
}
