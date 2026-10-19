"""Extract locally saved HTML/PDF into numbered blocks. Index publication is separate."""
import json,re
from pathlib import Path
from lxml import html
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent
CUSTOM={
 'CN-TAX-2026':'//*[@id="content"]',
 'CN-FX-2024':'//*[contains(@class,"content-details-main")]',
 'CN-FX-GUIDE':'//*[contains(@class,"content-details-main")]',
 'JP-DOCUMENTS':'//*[@id="main"]','JP-TARIFF':'//*[@id="main"]','JP-RCEP':'//*[@id="main"]',
 'US-IMPORT':'//article[1]','US-301':'//article[1]',
 'US-LOW-VALUE-PROPOSAL':'//pre',
 'VN-IMPORT':'//*[@id="content"]',
}
BLOCK_TAGS={'p','li','h1','h2','h3','h4','h5','h6','tr','pre','dt','dd','blockquote'}
def clean(s):return re.sub(r'[ \t\u00a0]+',' ',s).strip()

def html_blocks(data,sid):
    enc=re.search(br'charset=["\s]*([a-zA-Z0-9_-]+)',data[:8000])
    encoding=enc.group(1).decode() if enc else 'utf-8'
    tree=html.fromstring(data,parser=html.HTMLParser(encoding=encoding))
    for e in tree.xpath('//script|//style|//nav|//footer|//header|//noscript|//svg|//form|//button'):e.drop_tree()
    expr=CUSTOM.get(sid)
    matches=tree.xpath(expr) if expr else []
    if not matches:
        for expr in ['//main','//article','//*[@class="TRS_Editor"]','//*[@id="content"]','//body']:
            matches=tree.xpath(expr)
            if matches:break
    node=matches[0] if matches else tree
    if sid=='US-LOW-VALUE-PROPOSAL':
        return [{'text':clean(x),'section':'Federal Register notice','locator':f'paragraph {i+1}'} for i,x in enumerate(re.split(r'\n\s*\n',node.text_content())) if clean(x)]
    blocks=[];heading='Document body'
    for e in node.iter():
        if e.tag not in BLOCK_TAGS:continue
        if any(a.tag in BLOCK_TAGS for a in e.iterancestors() if a is not node):continue
        txt=clean(' '.join(e.itertext()))
        if not txt:continue
        if str(e.tag).startswith('h') and len(e.tag)==2:heading=txt
        elif re.match(r'^第[一二三四五六七八九十百]+[章条]',txt):heading=txt[:80]
        blocks.append({'text':txt,'section':heading,'locator':e.getroottree().getpath(e)})
    if not blocks:blocks=[{'text':clean(node.text_content()),'section':'Document body','locator':node.getroottree().getpath(node)}]
    return blocks

def run():
    summary=[]
    for r in json.loads((ROOT/'sources.json').read_text()):
        sid=r['source_id'];mp=ROOT/'fetch'/f'{sid}.json'
        meta=json.loads(mp.read_text()) if mp.exists() else {'status':'not_fetched'}
        row={'source_id':sid,'fetch_status':meta['status']}
        if meta['status']!='downloaded':summary.append(row);continue
        p=ROOT/meta['raw_path']
        if not p.stat().st_size:row['extraction_status']='empty_response';summary.append(row);continue
        if p.suffix=='.pdf':
            blocks=[{'text':clean(page.extract_text() or ''),'section':f'PDF page {i+1}','locator':f'page={i+1}'} for i,page in enumerate(PdfReader(p).pages)]
            method='pdf_text'
        else:blocks=html_blocks(p.read_bytes(),sid);method='html_dom'
        blocks=[dict(b,block_id=f'{sid}-B{i+1:04d}') for i,b in enumerate(blocks) if b['text']]
        chars=sum(len(b['text']) for b in blocks)
        row.update(extraction_status='candidate' if chars>=300 else 'thin_page',blocks=len(blocks),characters=chars,method=method)
        (ROOT/'extracted'/f'{sid}.json').write_text(json.dumps({'source_id':sid,'method':method,'blocks':blocks},ensure_ascii=False,indent=2)+'\n')
        (ROOT/'extracted'/f'{sid}.txt').write_text('\n\n'.join(f"[{b['block_id']}] {b['section']}\n{b['text']}" for b in blocks)+'\n')
        summary.append(row)
    (ROOT/'extraction_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    for r in summary:print(r['source_id'],r.get('extraction_status',r['fetch_status']),r.get('characters',''))

if __name__=='__main__':run()
