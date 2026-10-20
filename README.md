# CashWeave

An export-finance workspace for small Chinese trading businesses. CashWeave connects company cash, order evidence, document search and an AI conversation in one workflow.

## Companies, orders and cash planning

The default homepage lists saved companies. Choose **New company**, enter a name and dated opening CNY/USD balances, review them, then confirm. A new company starts with no orders or sample cash movements.

Inside a company, choose **New order** and enter the customer, goods, order currency/value, already received amount, next expected receipt and supplier payment. USD, EUR, GBP and CNY orders are supported; the cash forecast is in CNY using the explicit conversion assumption you enter. Unknown receipts stay unscheduled.

**Review and continue** previews the company-wide cash impact without saving. **Confirm and save** writes the order and its payment plan in one SQLite transaction. **Edit order** follows the same review flow; it replaces that order's future movements rather than duplicating them. Cancelled orders remain in history and contribute no future receipts or payments.

The dashboard, document upload scope and AI assistant use the selected company's saved records. Click **Analyze cash impact** on an order to start analysis with that order's context. Documents can be linked to any saved order, and confirmed AI receipt proposals update its expected payment plan. Company switching separates orders, documents, conversations and AI tasks.

The SQL schema and API are documented in [Database design](docs/DATABASE.md).

## Start the backend and frontend

After the one-time installation below, run these in two terminals from the repository root:

```bash
# Terminal A: loads tradex-rag/.env and opens port 8765
cd tradex-rag
./start.sh
```

```bash
# Terminal B: run from the repository root; opens port 5173
npm run dev
```

Open **http://127.0.0.1:5173/** for company management. Backend API reference: **http://127.0.0.1:8765/docs**. Keep both terminals running. Company and order tables are created automatically at startup; no separate SQL server or manual schema import is needed.

API keys belong in **`tradex-rag/.env`**. Company/order management and deterministic cash calculations work without a model key; AI answers require the configured model provider. See [OpenRouter configuration](#openrouter-and-multi-agent-configuration). Restart the backend after changing `.env`.

## First-time setup after cloning

Use **Node.js 20+ and Python 3.12**. The commands below target macOS, Linux or Windows with WSL2; on Windows, run both services inside WSL2. Python 3.12 is the reference environment for the binary embedding dependencies. A GPU, Docker, a separate database server and an API key are not needed for local retrieval.

### 1. Clone the repository

```bash
git clone https://github.com/a-wild-chocolate/Fintechathon.git
cd Fintechathon
node --version
python3.12 --version
```

Git names the cloned folder `Fintechathon`, even though the product is CashWeave. All paths below are relative to that folder. The frontend uses Node's built-in modules, so there is no `npm install` step.

### 2. Install the backend and create its configuration

```bash
cd tradex-rag
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
cp .env.example .env
```

Copy `.env.example` only during first-time setup; repeating the copy would overwrite your local settings. For the initial check, leave API keys empty and keep `TRADEX_CHAT_ENABLED=0`. The service will use local embeddings and return cited excerpts without paid model calls.

### 3. Download the embedding model and initialize the knowledge library

Run from `Fintechathon/tradex-rag` before starting the backend:

```bash
.venv/bin/python scripts/download_model.py
.venv/bin/python -m tradex_rag.cli seed
.venv/bin/python -m tradex_rag.cli drain
.venv/bin/python -m tradex_rag.cli stats
```

The first command downloads BAAI/bge-small-zh-v1.5 into `.models/` and checks its 512-dimensional output. Initial package installation and model download require network access. `seed` queues the 28 curated bilingual cards from `../knowledge_base/retrieval_ready.jsonl`; `drain` creates their keyword and vector indexes under `var/`. Repeating `seed` skips existing source IDs. The original public archive is tracked in Git; local databases, weights and company uploads are generated on each teammate's machine.

### 4. Start the backend — terminal A

From `Fintechathon/tradex-rag`:

```bash
./start.sh
```

Leave this terminal running. Open http://127.0.0.1:8765 for the bilingual library, or http://127.0.0.1:8765/docs for the API reference.

### 5. Start the frontend — terminal B

In a second terminal, change to the cloned `Fintechathon` folder:

```bash
npm run dev
```

Open **http://127.0.0.1:5173**. The Node server forwards `/api/*` to the backend on port 8765, and `/knowledge` opens the library through the same proxy. There is no browser-side API key or separate vector database to configure.

### 6. Verify the complete workflow — terminal C

From the repository root, with both services still running and both agent and legacy chat modes disabled:

```bash
npm run check
npm test
npm run check:integration
npm run build
```

The integration check uploads a synthetic payment document, waits for indexing, asks English and Chinese questions, follows version-specific source links and checks order scoping and English policy titles. It archives its test upload afterward. Backend unit tests run separately:

```bash
cd tradex-rag
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

Check the live service without opening its database in another process:

```bash
curl http://127.0.0.1:8765/api/health
curl http://127.0.0.1:5173/api/assistant/status
```

With chat disabled, the second response contains `"mode":"evidence"`. Try the manual upload and citation walkthrough under [Product flow](#product-flow).

## Start again on another day

Initialization is needed only once. Start `./start.sh` from `Fintechathon/tradex-rag` and `npm run dev` from `Fintechathon` in separate terminals. Stop either service with Ctrl+C. Keep the generated `.models/` and `var/` folders between sessions.

## OpenRouter and multi-agent configuration

The Coordinator delegates to Reconciliation, Cash-flow and Decision subagents through role-specific tool loops. See [the agent guide](docs/AGENTS.md) for architecture, tools, persistent clarification and the confirmation flow.

Edit **`Fintechathon/tradex-rag/.env`**, beside `start.sh`. Keep existing local settings and add or update:

```dotenv
TRADEX_AGENTS_ENABLED=1
TRADEX_MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key
TRADEX_MODEL=deepseek/deepseek-v4.1-flash
TRADEX_MODEL_CONCURRENCY=2
TRADEX_AGENT_MAX_CALLS=18
TRADEX_MODEL_MAX_TOKENS=4096
TRADEX_CHAT_ENABLED=0
```

The model output limit is configurable through `TRADEX_MODEL_MAX_TOKENS` (default: 4096). Truncated responses and invalid tool arguments are reported separately; failed provider requests are not automatically retried.

Restart the backend with `./start.sh`. `/api/assistant/status` reports `multi_agent` once the selected provider is configured. Without a key, document retrieval and source excerpts still work. To run the no-paid-inference integration check, set both `TRADEX_AGENTS_ENABLED=0` and `TRADEX_CHAT_ENABLED=0`, then restart.

Each role can use a different model through `TRADEX_MODEL_COORDINATOR`, `TRADEX_MODEL_RECONCILIATION`, `TRADEX_MODEL_CASH_FLOW` and `TRADEX_MODEL_DECISION`. Without overrides they share `TRADEX_MODEL`. The adapter preserves the same business workflows when changing providers.

### Direct Qwen or DeepSeek API

For Qwen, set `TRADEX_MODEL_PROVIDER=qwen`, `TRADEX_MODEL=qwen-plus`, `DASHSCOPE_API_KEY` and `DASHSCOPE_BASE_URL`. A Beijing workspace URL is `https://YOUR_WORKSPACE_ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`; Singapore uses `https://YOUR_WORKSPACE_ID.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`. Use the endpoint matching the key's workspace, following the [official documentation](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions).

For DeepSeek, set `TRADEX_MODEL_PROVIDER=deepseek`, `TRADEX_MODEL=deepseek-chat` and `DEEPSEEK_API_KEY`. The default base is `https://api.deepseek.com`. Clear any OpenRouter-specific role model overrides or `TRADEX_MODEL_BASE_URL` when changing provider. Both alternatives use the same four-role runtime.

Keys stay in **`tradex-rag/.env`**, never in frontend files or Git. A configured status confirms settings were loaded; actual provider connectivity and output quality require a real request, which may incur charges.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `python3.12` not found | Install Python 3.12, then create the virtual environment with that interpreter. |
| Model download fails or `embedding_failed` appears | Complete `scripts/download_model.py` with network access. Stop the backend, run `cli reindex` followed by `cli drain` using `.venv/bin/python -m tradex_rag.cli`, then restart. |
| No public policies are listed | Stop the backend, run `cli seed` and `cli drain` from `tradex-rag/`, then restart. |
| Qdrant storage is already accessed by another instance | Keep only one backend process. Stop it before `seed`, `drain`, `stats`, `query` or `reindex`; use the HTTP health endpoint while it runs. |
| Knowledge service offline / HTTP 503 | Start `tradex-rag/start.sh` and check that frontend and backend use the same backend port. |
| Port already in use | Stop the previous process or use the alternate-port commands below. |
| Assistant still reports `evidence` | Check the selected provider key and `TRADEX_AGENTS_ENABLED=1`, then restart with `./start.sh`. |
| Model request fails | Check the backend configuration, regional endpoint, key permissions, available model and account quota. |

To use different ports, run `TRADEX_RAG_PORT=8766 ./start.sh` in terminal A, then `PORT=5174 TRADEX_RAG_PORT=8766 npm run dev` in terminal B. Set `TRADEX_FRONTEND_URL=http://127.0.0.1:5174` when running the integration check. If `.env` also defines `TRADEX_RAG_PORT`, update that value to match.

`start.sh` loads `.env`; direct CLI commands do not. For CLI commands using custom embedding or storage settings, load them first in a POSIX shell with `set -a; . ./.env; set +a` from `tradex-rag/`.

See the [backend README](tradex-rag/README.md), [knowledge archive README](knowledge_base/README.md) and [verification record](docs/VERIFICATION.md) for implementation details and completed checks.

## Product flow

**Company overview → Select an order → Upload evidence → Confirm fields → Review cash impact → Discuss next steps.**

- **Overview** shows currency-specific balances, upcoming payments, a 56-day cash projection and orders requiring attention.
- **Documents** supports real uploads with an optional order association, processing status, company-document and public-policy views, and a direct **Ask AI** entry.
- **AI assistant** searches the selected document or the current order plus shared company records and public policies. Answers show numbered citations. Each citation opens the referenced file version, highlights the source passage and links to the original file or official policy page.

Chinese and English controls cover the frontend and knowledge workbench. Public policy cards have English display titles and bilingual summaries. Uploaded originals and quoted evidence retain their source language.

### Document-to-answer flow

1. Create a company and save an order.
2. Open **Documents**, upload the buyer's payment email or screenshot, and link it to the order.
3. Wait for processing to finish, then select **Ask AI**.
4. Answer any questions about missing amounts or dates and review the proposed fields.
5. Confirm the payment plan to update the order and cash forecast.
6. Open a numbered citation to inspect the source evidence.

A payment promise updates the expected receipt schedule; it does not record a bank receipt. Model credentials are required for extraction and AI analysis.

## Repository layout

```text
tradex-rag/                   Python API, MCP bridge, retrieval service and tests
knowledge_base/               Public sources and 28 curated bilingual policy cards
index.html                    Application shell
src/
  business-ui.js              Company, order, dashboard and AI workflow
  knowledge.js                Uploads, retrieval chat and citation viewer
  data.js                     Bilingual copy and business templates
  finance.js                  Deterministic cash calculations
  partial-payment.js          Email-field clarification demo
  followups.js                Reminder and event-demo logic
  storage.js                  Backend workspace persistence and browser cache
  icons.js                    Local SVG icons
  styles.css                  Base components
  clarity.css                 Finance-workspace layouts
  knowledge.css               Library and source-viewer styles
tests/                        Business-logic unit tests
scripts/
  serve.js                    Static server and local API proxy
  build.js                    Static build
  check.js                    Syntax validation
  check-integration.js        Live backend checks without paid inference
docs/
  API.md                      Frontend/backend contracts
  VERIFICATION.md             Verification record and remaining setup
```

`dist/`, `output/`, `previews/`, logs, process IDs, dependency folders, backend `var/` data, downloaded `.models/` and local credentials are excluded from Git. The repository includes source code, tests and their fixtures, English setup documentation and public knowledge sources. Runtime databases and private uploads are created locally.

## State and deployment

Company records, orders, payment schedules and conversation state are persisted by the backend. Source files, indexed passages and document versions are stored by the backend in SQLite and Qdrant. Uploading a document does not itself modify financial balances; the order workflow requires field confirmation.

`dist/` contains static frontend assets. **GitHub Pages alone does not run the API proxy or Python backend.** For the connected application, run the Node server and RAG service together, or configure your hosting platform to forward `/api/*` and `/knowledge` to the backend. The current server binds to localhost; shared deployment needs an authenticated application boundary.

This directory is the repository root. Both services and the knowledge archive use paths relative to it; the surrounding desktop folders are not required.

### Deep Agents, public search and sandbox

TradeX now uses the open-source Deep Agents harness for its Coordinator and three business subagents. Human clarification, background task progress and cited answers use the same frontend workflow. See [agent setup](docs/AGENTS.md#local-setup) for the optional OpenSandbox service and public web search. Main model credentials remain in `tradex-rag/.env`; web search reuses `OPENROUTER_API_KEY`.

## Email screenshot workflow

Upload a PNG, JPG or WEBP through **Documents**, link it to the order, and choose **Ask AI** after indexing. The backend sends the image directly to the configured vision model, stores the transcription and payment fields with the source version, and indexes them for retrieval. Missing amount or date fields remain empty until the assistant asks the user. Confirmation updates the expected receipt and cash projection, while the bank balance and total outstanding receivable remain unchanged. Citation buttons open the original screenshot alongside the extracted text.

Configure `TRADEX_MODEL_VISION` in `tradex-rag/.env`. It uses the existing provider and API key. OpenRouter defaults to `qwen/qwen3.5-plus-20260420` for screenshots; the conversational agents keep their separately configured DeepSeek models. Other providers use `TRADEX_MODEL` unless overridden with a vision-capable model. Image extraction is cached per source version so an indexing retry reuses the result; changing models does not rewrite existing evidence. Upload a new document or source version to analyze it again. No separate OCR service is required.

The bell opens a contextual event list. Opening it marks the displayed events as read; the alerts remain available. Expand an event to inspect its cash impact, open its order or explicitly start AI analysis. Unchanged financial alerts retain their read state across unrelated workspace versions.

## Repository hygiene

Presentation kits, recordings, local demo assets and standalone UI previews are excluded from version control. Runtime databases, uploaded documents, model caches and credentials stay in ignored local directories. Public policy sources and small synthetic test fixtures remain available so retrieval and regression tests are reproducible. The separate security experiment directory is maintained independently.
