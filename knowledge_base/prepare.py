"""Normalize reviewed web-extraction fallbacks and add source-level curation metadata."""
import json,re
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parent
WINDOWS={'TH-IMPORT':(123,154),'AU-CHAFTA':(275,600),
         'CN-SZ-INSURANCE':(18,41),'CN-GZ-INSURANCE':(33,60)}

def run():
    for sid,(lo,hi) in WINDOWS.items():
        paths=sorted((ROOT/'web_extracts').glob(sid+'*.txt'));lines={}
        for p in paths:
            for m in re.finditer(r'^L(\d+)(?:@P[\d-]+)?: (.*)$',p.read_text(),re.M):
                n=int(m[1]);s=re.sub(r'cite[^†]*†([^]*)',r'\1',m[2]).strip()
                if lo<=n<=hi and s and not s.startswith('[Input'):lines[n]=s
        heading='Selected source excerpt';blocks=[]
        for n,s in sorted(lines.items()):
            if s.startswith('#'):heading=s.lstrip('# ')
            blocks.append({'block_id':f'{sid}-W{n:04d}','text':s,'section':heading,'locator':f'web extracted line {n}'})
        if blocks:
            v={'source_id':sid,'method':'web_tool_excerpt','coverage':'selected lines, not full original','blocks':blocks}
            (ROOT/'extracted'/f'{sid}.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
            (ROOT/'extracted'/f'{sid}.txt').write_text('\n\n'.join(f"[{b['block_id']}] {b['section']}\n{b['text']}" for b in blocks)+'\n')
    records=json.loads((ROOT/'sources.json').read_text())
    for r in records:
        sid=r['source_id'];p=ROOT/'extracted'/f'{sid}.json'
        extracted=json.loads(p.read_text()) if p.exists() else {}
        available=bool(extracted.get('blocks'))
        r.update(content_status='text_available' if available else 'reference_link_only',
                 extraction_method=extracted.get('method'),content_coverage=extracted.get('coverage','extracted body' if available else None),
                 source_text_path=f'extracted/{sid}.txt' if available else None,
                 review_due=(date.fromisoformat(r['collected_on'])+timedelta(days=r['review_interval_days'])).isoformat(),
                 review_scope='Selected operational claims checked against source; no exhaustive amendment audit',
                 agent_rule_authority=False,live_check_before_rate_use=True)
        if sid=='US-301':r.update(allowed_use='selected_claims_only',review_note='Legacy Section 321 paragraphs are excluded from default retrieval. Check current HTS Chapter 99 and CBP notices per entry.')
        if sid=='JP-RCEP':r.update(allowed_use='selected_claims_only',review_note='Use China-to-Japan origin procedure only. Do not reuse the page member-status list as a current RCEP membership register.')
        if sid=='VN-IMPORT':r.update(allowed_use='historical_reference',legal_status='amendment_check_needed',review_note='Page cites older laws, a 20,000 VND fee and processing times. Current amendments, fees and timing are not verified; excluded from default answer collection.',language='en')
        if sid=='CN-GZ-INSURANCE':r.update(published_date='2026-06-30',region='Guangzhou',review_note='Check actual policy and enrollment status; notice does not establish a payout or coverage for an arbitrary enterprise.')
        if sid=='CN-SZ-INSURANCE':r.update(region='Shenzhen',review_note='Specified coverage ended 30 September 2026; not a current enrollment offer.')
        if sid in ['US-HTS','RCEP-PORTAL','EU-GPSR','AU-IMPORT']:r.update(allowed_use='lookup_or_recovery_only')
        if sid=='ICC-DAP-DDP':r.update(reuse_scope='Public explanatory article: store source link and original short paraphrase; do not embed full article or paid Incoterms rules.')
    (ROOT/'sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print('Available text:',sum(r['content_status']=='text_available' for r in records),'of',len(records))

if __name__=='__main__':run()
