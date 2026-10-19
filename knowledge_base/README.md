# TradeX public trade knowledge

This source archive supports Chinese small export businesses with document, payment, origin and destination-market guidance. The collection was assembled on **18 October 2026** and contains **34 source records, 28 curated bilingual retrieval cards and 446 candidate source chunks**.

## Contents

| Path | Purpose |
| --- | --- |
| `retrieval_ready.jsonl` | Default backend seed: 28 curated cards with Chinese and English summaries, English display titles and citations |
| `cards/` | Individual copies of the curated cards |
| `titles_en.json` | Canonical English display titles, preserved when rebuilding |
| `sources.json`, `source_catalog.csv` | Source URLs, publishers, jurisdictions, dates and permitted uses |
| `raw/`, `fetch/` | Downloaded public-source snapshots and collection metadata |
| `extracted/`, `web_extracts/` | Parsed blocks and selected excerpts with citation locations |
| `chunks/source_candidates.jsonl` | Unreviewed candidate chunks, excluded from default ingestion |
| `qdrant_payloads.jsonl` | Payload examples; these contain metadata, not embedding vectors |
| `index.html` | Offline source catalogue |
| `query_examples.jsonl`, `validation_report.json` | Keyword retrieval fixtures and source-reference checks |

Coverage includes China, the US, EU, UK, Singapore, Japan, Australia, Thailand, RCEP and trade terms, with regional export-insurance references. Vietnam currently has historical reference material only. Source status and dates determine inclusion: expired Shenzhen insurance coverage and a US proposal remain outside the default answer cards.

The archive retains public documents and selected excerpts with their original URLs. ICC full-text snapshots are excluded; its trade-term card contains an original bilingual summary and a source link. Private company uploads belong in the backend's ignored runtime storage, not this archive.

## Use with the backend

From `tradex-rag/`, after installing its dependencies and downloading the local model:

```bash
.venv/bin/python -m tradex_rag.cli seed
.venv/bin/python -m tradex_rag.cli drain
```

The backend imports only `retrieval_ready.jsonl`. Each card retains source and applicability metadata. `summary_zh`, `summary_en` and `evidence_refs` describe source material; `tradex_workflow` and `cash_effect` describe TradeX product suggestions.

## Rebuild and validate

From this directory:

```bash
python3 build.py
python3 validate.py
python3 search.py "partial payment export documents" --market CN
```

Rebuilding uses saved extracted blocks, `cards_data.py` and `titles_en.json`; it does not require model calls or network access. Validation checks citation references, English titles and keyword query fixtures. It does not refresh policy facts.

For source updates, `collect.py` downloads registered URLs, `extract.py` parses downloaded files and `prepare.py` restores selected web excerpts. Extraction uses `lxml` and `pypdf`, available in the backend environment. Run `build.py` and `validate.py` afterward. `seed_sources.py` initializes the source register and overwrites it, so it is not part of routine rebuilds.

These dated snapshots provide document guidance and lookup paths. Product-specific tariff rates and eligibility require the applicable product, origin, business date and current official source.
