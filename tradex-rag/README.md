# TradeX RAG service

The Python backend stores versioned business documents in SQLite, indexes passages in Qdrant and provides cited retrieval to the TradeX frontend and MCP clients. Public policy cards and company uploads share a retrieval interface with separate visibility and order scopes.

## Installation

From this directory, using Python 3.12 or newer:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
cp .env.example .env
.venv/bin/python scripts/download_model.py
.venv/bin/python -m tradex_rag.cli seed
.venv/bin/python -m tradex_rag.cli drain
./start.sh
```

The model download requires network access once. Subsequent local indexing uses BAAI/bge-small-zh-v1.5 through FastEmbed on CPU. No API key is needed for local retrieval. `seed` imports the 28 curated bilingual cards from `../knowledge_base/retrieval_ready.jsonl`; repeating it skips existing source IDs. `drain` processes the persisted indexing queue.

Open http://127.0.0.1:8765 for the library workbench or run `npm run dev` from the repository root for the finance application. The HTTP API description is available at http://127.0.0.1:8765/docs.

Embedded Qdrant has one owning process. Stop the server before running CLI commands that open the same library. MCP clients use the running HTTP service through `./mcp.sh` instead of opening its storage directly.

## Qwen answers

Set the following in this directory's `.env`, then restart `./start.sh`:

```dotenv
TRADEX_EMBEDDING=bge-local
DASHSCOPE_API_KEY=your_model_studio_api_key
DASHSCOPE_BASE_URL=your_regional_openai_compatible_base_url
TRADEX_CHAT_ENABLED=1
TRADEX_CHAT_MODEL=qwen-plus
```

Use the compatible endpoint from the same Model Studio region as the key, ending in `/compatible-mode/v1`. With chat disabled, answers display retrieved excerpts and citations. With chat enabled, Qwen generates an evidence-based answer and the service checks its cited source IDs. Credentials remain in the backend; `.env` is ignored by Git.

The optional hosted embedding configuration is documented in `.env.example`. Changing embedding models requires reindexing into the corresponding vector collection. `start.sh` reads `.env`; for direct CLI commands using custom settings, export those variables in the terminal first.

## Data and processing

Upload → immutable source version → persisted job → parsing → parent/child chunks → keyword and vector indexing → searchable document and event.

- SQLite owns document metadata, versions, write leases, processing jobs, events and FTS5 keyword search.
- Qdrant stores the embedding vectors; hybrid search combines vector and keyword rankings and returns parent context with source locations.
- Parsers support TXT, Markdown, EML, text-readable PDF, DOCX, CSV and XLSX. Image-only PDFs require OCR outside the current parser.
- Local BGE child chunks use a 350-token window and 50-token overlap; parent sections preserve page, paragraph and row references.
- Document edits use expiring write leases and version checks. Original files remain available for citation inspection.
- The assistant can scope retrieval to a selected document, order, company or public policy collection. Retrieval does not commit financial transactions.

Runtime files are created under `var/`, and downloaded models under `.models/`. Neither directory is included in the repository. The server uses a configured local tenant; shared deployment requires application authentication.

## Verification

```bash
.venv/bin/python -m pytest -q
python3 ../knowledge_base/validate.py
```

The local-model tokenizer test skips when model weights have not been downloaded. From the repository root, `npm run check:integration` checks uploads, bilingual retrieval and citation downloads through the running frontend proxy; keep `TRADEX_CHAT_ENABLED=0` for this check.

See [research and design notes](docs/research_and_design.txt) for storage, chunking and MCP decisions, and [frontend API contracts](../docs/API.md) for integration details. `requirements-tested.txt` records the earlier development environment; `pyproject.toml` declares installation dependencies.
