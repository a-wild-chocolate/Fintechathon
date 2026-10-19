# TradeX RAG service

The Python backend stores versioned business documents in SQLite, indexes passages in Qdrant and provides cited retrieval to the TradeX frontend and MCP clients. Public policy cards and company uploads share a retrieval interface with separate visibility and order scopes.

## Installation

For a complete clone-to-browser walkthrough, see the [root README](../README.md#first-time-setup-after-cloning). Use Python 3.12 as the reference environment. Commands below run from `Fintechathon/tradex-rag` in macOS, Linux or WSL2:

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

## Main agent and subagents

Configure OpenRouter in this directory's `.env` using the [root setup guide](../README.md#openrouter-and-multi-agent-configuration). The provider adapter also supports direct Qwen and DeepSeek APIs. The Coordinator delegates to Reconciliation, Cash-flow and Decision; tools use the existing MCP bridge and HTTP workflows. [Agent architecture and tool contracts](../docs/AGENTS.md) describe the implementation.

Without a configured key, retrieval excerpts remain available. With `TRADEX_AGENTS_ENABLED=1` and the selected provider configured, `/api/assistant/chat` runs the multi-agent workflow. `TRADEX_CHAT_ENABLED` controls the older single-call Qwen path and should remain `0` for the multi-agent application.

Keep `.env` local. `start.sh` reads it; direct CLI commands require exported environment variables when using non-default settings. Agent run and proposal state is stored in ignored `var/agents.sqlite3`.

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

The local-model tokenizer test skips when model weights have not been downloaded. From the repository root, `npm run check:integration` checks uploads, bilingual retrieval and citation downloads through the running frontend proxy; keep `TRADEX_AGENTS_ENABLED=0` and `TRADEX_CHAT_ENABLED=0` for this check. Run `.venv/bin/python -m pytest tests/test_agent_stack.py -m integration -q` for the actual local MCP/multi-agent contract test with mocked model replies.

See [research and design notes](docs/research_and_design.txt) for storage, chunking and MCP decisions, and [frontend API contracts](../docs/API.md) for integration details. `requirements-tested.txt` records the earlier development environment; `pyproject.toml` declares installation dependencies.
