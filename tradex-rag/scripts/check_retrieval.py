"""Small transparent retrieval smoke test over the collected public cards."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tradex_rag.service import Library
root=Path(__file__).resolve().parents[1];lib=Library();checks=[]
try:
    cases=[json.loads(l) for l in (root.parent/'knowledge_base/query_examples.jsonl').read_text().splitlines()]
    for case in cases:
        r=lib.search(case['query'],lib.settings.tenant,market=case['market'],limit=5,as_of='2026-10-18')
        hits=[h['metadata'].get('card_id','private_document') for h in r['results']]
        checks.append({**case,'retrieved_top5':hits,'expected_in_top5':case['expected_top3_card'] in hits,'semantic_available':r['semantic_available']})
    report={'test_type':'10 known-card retrieval smoke queries; not a held-out benchmark','model':lib.embedding.model_id,
            'stats':lib.stats(lib.settings.tenant),'checks':checks,'passed':sum(r['expected_in_top5'] for r in checks),'total':len(checks)}
    (root/'docs/retrieval_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'passed':report['passed'],'total':report['total'],'model':report['model'],'failures':[c for c in checks if not c['expected_in_top5']]},ensure_ascii=False,indent=2))
finally:lib.close()
