"""Offline keyword smoke test over curated cards, not a vector-retrieval implementation."""
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
RCEP={'CN','JP','SG','AU','VN','TH','KR','MY','ID','NZ','PH','BN','KH','LA','MM'}
def search(query,market=None,limit=5):
    cards=[json.loads(x) for x in (ROOT/'retrieval_ready.jsonl').read_text().splitlines()]
    terms=re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]+',query.lower())
    results=[]
    for c in cards:
        if market and c['jurisdiction'] not in {market,'GLOBAL',*(['RCEP'] if market in RCEP else [])}:continue
        text=c['embedding_text'].lower()
        score=sum(3 if t in text else 0 for t in terms)
        score+=sum(2 for k in c['keywords'] if k.lower() in query.lower())
        if score:results.append(dict(card_id=c['card_id'],title=c['title'],score=score,source_url=c['source_url'],summary=c['summary_zh'],required_order_fields=c['required_order_fields']))
    return sorted(results,key=lambda x:-x['score'])[:limit]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('--market');p.add_argument('--limit',type=int,default=5);a=p.parse_args()
    print(json.dumps(search(a.query,a.market,a.limit),ensure_ascii=False,indent=2))
