import argparse,json
from pathlib import Path
from .config import Settings
from .service import Library

def seed(lib,path):
    existing={d['source_key'] for d in lib.list_documents('public')}
    count=0
    for line in path.read_text().splitlines():
        card=json.loads(line);key=card['card_id']
        if key in existing:continue
        # Selected summaries enter search; 446 unreviewed raw slices stay in the source archive.
        text=card['embedding_text']+'\n\nCashWeave workflow suggestion (not a policy clause):\n'+card['tradex_workflow']
        fields=['title_en','card_id','source_id','source_url','source_title','publisher','jurisdiction','effective_from','effective_to','review_due','allowed_use','evidence_refs','required_order_fields','cash_effect','tradex_workflow']
        metadata={k:card.get(k) for k in fields};metadata['source_kind']='curated_policy_card'
        lib.create(key+'.txt',text.encode(),card['title'],'public',metadata,source_key=key);count+=1
    return count

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('seed');p.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[2]/'knowledge_base/retrieval_ready.jsonl')
    sub.add_parser('drain');sub.add_parser('stats');sub.add_parser('reindex')
    p=sub.add_parser('query');p.add_argument('text');p.add_argument('--market');p.add_argument('--mode',default='hybrid')
    p=sub.add_parser('upload');p.add_argument('path',type=Path);p.add_argument('--title');p.add_argument('--order')
    args=parser.parse_args();lib=Library()
    try:
        if args.command=='seed':result={'queued':seed(lib,args.source)}
        elif args.command=='drain':
            n=0
            while lib.process_next():
                n+=1;print(f'Processed job {n}',flush=True)
            result=lib.stats(lib.settings.tenant)
        elif args.command=='stats':result=lib.stats(lib.settings.tenant)
        elif args.command=='reindex':result={'queued':lib.queue_reindex()}
        elif args.command=='query':result=lib.search(args.text,lib.settings.tenant,market=args.market,mode=args.mode)
        elif args.command=='upload':result=lib.create(args.path.name,args.path.read_bytes(),args.title or args.path.name,lib.settings.tenant,{'order_id':args.order,'source_kind':'user_upload'})
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:lib.close()
if __name__=='__main__':main()
