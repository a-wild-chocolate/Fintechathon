"""Build citation-bearing retrieval cards, candidate chunks and a local source catalogue."""
import csv,html,json,re
from pathlib import Path
from cards_data import CARDS
ROOT=Path(__file__).resolve().parent

def write_jsonl(path,rows):
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def run():
    sources=json.loads((ROOT/'sources.json').read_text());by_id={r['source_id']:r for r in sources}
    titles=json.loads((ROOT/'titles_en.json').read_text())
    cards=[];candidates=[];issues=[]
    for s in sources:
        sid=s['source_id'];path=ROOT/'extracted'/f'{sid}.json'
        if not path.exists() or sid=='ICC-DAP-DDP':continue
        doc=json.loads(path.read_text());group=[];length=0;section=''
        def flush():
            if not group:return
            idx=sum(c['source_id']==sid for c in candidates)+1
            candidates.append(dict(chunk_id=f'{sid}-C{idx:04d}',source_id=sid,source_url=s['url'],
                title=s['title'],jurisdiction=s['jurisdiction'],language=s['language'],topic=s['topic'],
                source_type=s['source_type'],legal_status=s['legal_status'],allowed_use=s['allowed_use'],
                collected_on=s['collected_on'],effective_from=s['effective_from'],effective_to=s['effective_to'],
                section=section,source_block_ids=[b['block_id'] for b in group],locators=[b['locator'] for b in group],
                text='\n\n'.join(b['text'] for b in group),parent_path=f'extracted/{sid}.json',
                extraction_method=doc['method'],index_status='candidate_not_default',embedding_status='not_generated'))
        for b in doc['blocks']:
            if group and (length+len(b['text'])>2400 or b['section']!=section):flush();group=[];length=0
            group.append(b);length+=len(b['text']);section=b['section']
        flush()
    for c in CARDS:
        s=by_id[c['source_id']];p=ROOT/'extracted'/f"{c['source_id']}.json"
        blocks=json.loads(p.read_text())['blocks'] if p.exists() else []
        hits=[]
        for term in c['anchor_terms']:
            found=[b for b in blocks if term.lower() in b['text'].lower()]
            if not found and c['source_id']!='ICC-DAP-DDP':issues.append(f"{c['card_id']}: missing evidence anchor {term}")
            for b in found[:3]:
                if b['block_id'] not in [x['block_id'] for x in hits]:hits.append(b)
        card={**c,'title_en':titles[c['card_id']],'jurisdiction':s['jurisdiction'],'source_title':s['title'],'source_url':s['url'],
              'publisher':s['publisher'],'source_type':s['source_type'],'source_language':s['language'],
              'topic':s['topic'],'collection':'tradex_public_trade','visibility':'public','tenant_id':None,
              'collected_on':s['collected_on'],'published_date':s['published_date'],
              'effective_from':s['effective_from'],'effective_to':s['effective_to'],
              'review_due':s['review_due'],'legal_status':s['legal_status'],'allowed_use':s['allowed_use'],
              'content_kind':'original_bilingual_summary','review_status':'selected_claims_source_checked',
              'workflow_status':'tradex_design_suggestion','rule_publication_status':'reference_only',
              'embedding_status':'not_generated','version':'2026-10-18-v0.1',
              'evidence_access':'source_link' if c['source_id']=='ICC-DAP-DDP' else 'local_excerpt',
              'evidence_refs':[{'block_id':b['block_id'],'locator':b['locator'],'path':f"extracted/{c['source_id']}.json"} for b in hits],
              'refresh_before_use':['tariff_rate','eligibility_decision','deadline_execution'],
              'agent_roles':['coordinator','reconciliation','cash_flow','decision','review']}
        card['embedding_text']='\n'.join([card['title'],card['summary_zh'],card['summary_en'],'Keywords: '+', '.join(card['keywords'])])
        if not card['evidence_refs'] and c['source_id']=='ICC-DAP-DDP':
            card['evidence_refs']=[{'source_url':s['url'],'locator':'Public explanation of DAP and DDP import clearance'}]
        cards.append(card)
        (ROOT/'cards'/f"{card['card_id']}.json").write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
    if issues:raise ValueError('\n'.join(issues))
    write_jsonl(ROOT/'retrieval_ready.jsonl',cards)
    write_jsonl(ROOT/'chunks'/'source_candidates.jsonl',candidates)
    write_jsonl(ROOT/'qdrant_payloads.jsonl',[{'id':i+1,'payload':c} for i,c in enumerate(cards)])
    fields=['source_id','jurisdiction','title','publisher','url','source_type','topic','language','published_date','effective_from','effective_to','collected_on','review_due','allowed_use','content_status','extraction_method','source_text_path','review_note']
    with (ROOT/'source_catalog.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(sources)
    snapshots=sum(json.loads(p.read_text()).get('status')=='downloaded' and json.loads(p.read_text()).get('bytes',0)>0 for p in (ROOT/'fetch').glob('*.json'))
    stats=dict(collected_on='2026-10-18',source_records=len(sources),nonempty_raw_downloads=snapshots,
               sources_with_extracted_text=sum(s['content_status']=='text_available' for s in sources),
               curated_retrieval_cards=len(cards),candidate_source_chunks=len(candidates),
               web_excerpt_sources=sum(s['extraction_method']=='web_tool_excerpt' for s in sources),
               reference_link_only=[s['source_id'] for s in sources if s['content_status']=='reference_link_only'],
               default_excluded=[s['source_id'] for s in sources if s['allowed_use'] in ['historical_reference','monitoring_only','lookup_or_recovery_only']],
               paid_model_calls=0,embeddings_generated=0,qdrant_uploaded=False)
    (ROOT/'collection_report.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    def esc(v):return html.escape(str(v or '—'))
    rows=''.join(f'<tr data-market="{esc(s["jurisdiction"])}"><td>{esc(s["source_id"])}</td><td>{esc(s["jurisdiction"])}</td><td><a href="{esc(s["url"])}">{esc(s["title"])}</a><small>{esc(s["publisher"])}</small></td><td>{esc(s["source_type"])}</td><td>{esc(s["allowed_use"])}</td><td>{esc(s["content_status"])}<small>{esc(s.get("review_note"))}</small></td></tr>' for s in sources)
    cards_html=''.join(f'<article data-market="{esc(c["jurisdiction"])}"><small>{esc(c["jurisdiction"])} · {esc(c["card_id"])}</small><h3>{esc(c["title"])}</h3><p>{esc(c["summary_zh"])}</p><p class="en">{esc(c["summary_en"])}</p><p><b>Agent workflow</b><br>{esc(c["tradex_workflow"])}</p><p><b>需要的订单字段</b><br>{esc(", ".join(c["required_order_fields"]))}</p><a href="{esc(c["source_url"])}">官方来源</a> · <a href="cards/{esc(c["card_id"])}.json">结构化条目</a></article>' for c in cards)
    markets=sorted(set(s['jurisdiction'] for s in sources))
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>TradeX 外贸知识库 · 第一批</title><style>
body{font:16px/1.7 system-ui,sans-serif;color:#1d3d34;background:#f5f8f5;margin:0}main{max-width:1200px;margin:auto;padding:40px 24px}h1{font-size:34px}p{max-width:1000px}a{color:#24745c}small{display:block;color:#62776c;font-size:13px}input,select{font:inherit;padding:10px;border:1px solid #b7c9bf;border-radius:8px;background:white}input{width:min(500px,70%)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}article{background:white;border:1px solid #dae4dd;border-radius:12px;padding:22px}.en{font-size:14px;color:#52685d}table{border-collapse:collapse;width:100%;background:white;font-size:13px}td,th{text-align:left;padding:12px;border-bottom:1px solid #dbe5df;vertical-align:top}.table{overflow:auto}.toolbar{position:sticky;top:0;background:#f5f8f5;padding:12px 0;display:flex;gap:10px}h2{margin-top:36px}[hidden]{display:none!important}</style><main>
<small>TradeX · PUBLIC TRADE KNOWLEDGE · 2026-10-18</small><h1>面向小微出口企业的外贸知识库</h1>
<p>围绕中国出口端、目的国清关与税费、原产地、单证和收汇，提供可追溯的政策资料及 Agent 检索卡片。用途是补齐业务信息、准备资料和建立有条件的资金情景；付款记录由企业资料确认。</p>
<p>COUNT 个来源记录 · CARDCOUNT 条检索卡片。网页/PDF原文、正文及引用位置保存在同一目录。税率须按商品、原产地和进口日期查询；已过期保障期和征求意见稿不进入默认回答。</p>
<p><a href="source_catalog.csv">下载来源目录 CSV</a>　<a href="retrieval_ready.jsonl">检索卡片 JSONL</a>　<a href="README.md">接入与覆盖说明</a></p>
<div class="toolbar"><input id="q" placeholder="搜索：英国 VAT / RCEP / 部分付款…" aria-label="搜索"><select id="market" aria-label="市场"><option value="">全部市场</option>OPTIONS</select></div>
<h2>可检索业务知识</h2><div class="grid">CARDS</div>
<h2>完整来源与采集状态</h2><div class="table"><table><thead><tr><th>ID</th><th>市场</th><th>来源</th><th>类型</th><th>用途</th><th>正文状态</th></tr></thead><tbody>ROWS</tbody></table></div>
<p>来源内容与 TradeX 建议分开保存；“已采集”表示本次取得的资料，不代表完成所有修法和商品适用性核查。尚未运行付费模型或上传到向量数据库。</p></main><script>
const q=document.querySelector('#q'),market=document.querySelector('#market');function filter(){for(const e of document.querySelectorAll('[data-market]'))e.hidden=!!((market.value&&e.dataset.market!==market.value)||!e.textContent.toLowerCase().includes(q.value.toLowerCase()));}q.addEventListener('input',filter);market.addEventListener('change',filter);
</script></html>'''
    document=document.replace('CARDCOUNT',str(len(cards))).replace('COUNT',str(len(sources))).replace('OPTIONS',''.join(f'<option>{esc(m)}</option>' for m in markets)).replace('CARDS',cards_html).replace('ROWS',rows)
    (ROOT/'index.html').write_text(document)
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__=='__main__':run()
