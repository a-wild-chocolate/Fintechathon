"""Download the explicit public-source list; preserve raw responses and fetch metadata.
No crawling, model calls, embedding requests, or writes to the application database.
"""
import argparse, concurrent.futures, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def fetch(record):
    sid=record['source_id']
    meta={'source_id':sid,'requested_url':record['url'],'retrieved_at':datetime.now(timezone.utc).isoformat()}
    try:
        req=urllib.request.Request(record['url'],headers={'User-Agent':'TradeX-Research/0.1 (public policy reference collection)','Accept-Language':'en,zh;q=0.8'})
        with urllib.request.urlopen(req,timeout=35) as response:
            body=response.read()
            mime=response.headers.get('Content-Type','')
            ext='pdf' if body.startswith(b'%PDF') else 'html'
            path=ROOT/'raw'/f'{sid}.{ext}'
            path.write_bytes(body)
            meta.update(status='downloaded',http_status=response.status,final_url=response.url,content_type=mime,
                        bytes=len(body),raw_path=str(path.relative_to(ROOT)),last_modified=response.headers.get('Last-Modified'),
                        etag=response.headers.get('ETag'))
    except Exception as exc:
        meta.update(status='fetch_failed',error=f'{type(exc).__name__}: {exc}')
    (ROOT/'fetch'/f'{sid}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    return sid,meta['status'],meta.get('bytes',0)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='*');args=parser.parse_args()
    for d in ['raw','fetch','extracted','chunks','cards']:(ROOT/d).mkdir(exist_ok=True)
    records=json.loads((ROOT/'sources.json').read_text())
    if args.only: records=[r for r in records if r['source_id'] in args.only]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(fetch,records):print(*result,flush=True)
