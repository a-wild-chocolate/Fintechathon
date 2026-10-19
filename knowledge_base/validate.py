"""Validate saved evidence references and a small offline keyword-retrieval fixture."""
import json
from pathlib import Path
from search import search
ROOT=Path(__file__).resolve().parent
def rows(name):
    return [json.loads(line) for line in (ROOT/name).read_text().splitlines()]
sources={s['source_id']:s for s in json.loads((ROOT/'sources.json').read_text())}
cards=rows('retrieval_ready.jsonl')
assert len({c['card_id'] for c in cards})==len(cards)
for card in cards:
    assert card['title_en'].strip()
    source=sources[card['source_id']]
    assert card['source_url']==source['url']
    assert card['allowed_use'] in {'evidence_retrieval','selected_claims_only'}
    assert card['evidence_refs']
    # ICC full text is retained only in the local working copy, not redistributed.
    if card['source_id']=='ICC-DAP-DDP' and 'path' not in card['evidence_refs'][0]:continue
    if card['source_id']=='ICC-DAP-DDP' and not (ROOT/card['evidence_refs'][0]['path']).exists():continue
    for ref in card['evidence_refs']:
        blocks=json.loads((ROOT/ref['path']).read_text())['blocks']
        assert any(b['block_id']==ref['block_id'] for b in blocks)
checks=[]
for case in rows('query_examples.jsonl'):
    found=[r['card_id'] for r in search(case['query'],case['market'],3)]
    checks.append({**case,'retrieved':found,'passed':case['expected_top3_card'] in found})
report={'reference_checks_passed':True,'cards_checked':len(cards),'keyword_queries':checks,
        'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'evaluation_scope':'File and citation integrity plus offline keyword smoke tests; no vector or LLM evaluation.'}
(ROOT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='keyword_queries'},ensure_ascii=False,indent=2))
assert all(c['passed'] for c in checks)
