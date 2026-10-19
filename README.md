# TradeX

An export-finance workspace for small Chinese trading businesses. TradeX connects company cash, order evidence, document search and an AI conversation in one workflow.

## First-time setup after cloning

Use **Node.js 20+ and Python 3.12**. The commands below target macOS, Linux or Windows with WSL2; on Windows, run both services inside WSL2. Python 3.12 is the reference environment for the binary embedding dependencies. A GPU, Docker, a separate database server and an API key are not needed for local retrieval.

### 1. Clone the repository

```bash
git clone https://github.com/a-wild-chocolate/Fintechathon.git
cd Fintechathon
node --version
python3.12 --version
```

Git names the cloned folder `Fintechathon`, even though the product is TradeX. All paths below are relative to that folder. The frontend uses Node's built-in modules, so there is no `npm install` step.

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
- **Notifications** demonstrate event-based updates and scheduled follow-ups using the browser's demo date.

Chinese and English controls cover the frontend and knowledge workbench. Public policy cards have English display titles and bilingual summaries. Uploaded originals and quoted evidence retain their source language.

### Try the document-to-answer flow

1. Open **Documents** and upload `demo/harbour-payment-confirmation.txt`.
2. Associate it with **TF-26104**, then wait for **Searchable**.
3. Click **Ask AI** beside the file.
4. Ask: “What amount will Harbour Supplies pay, on which date, and what remains unconfirmed?”
5. Open a numbered citation to inspect the source passage and download that exact version.
6. Switch to Chinese and ask: “客户付款金额、日期和余款安排是什么？”

With a configured model, the Coordinator can delegate analysis to specialists and propose fields for explicit confirmation. **Confirm and update dashboard** updates the expected receipt schedule; the follow-up conversation explains its cash impact. Without a key, this walkthrough returns retrieved excerpts.

The file is synthetic: it describes a USD 6,000 payment promise for 29 October 2026 and an unscheduled USD 6,000 remainder. Retrieval does not turn that promise into a confirmed bank receipt.

### Partial-payment clarification demo

The order workflow also contains a local field-confirmation demo. Select Harbour Supplies and use `demo/buyer-partial-payment.txt` or the sample button. Its email omits the amount and date; the local parser requests those fields before confirmation. Replies such as “6000美元” and “10月29日” complete the draft. Confirmation updates the demo order and cash projection. The template demo remains available without a key. For the real agent path, upload the email through Documents, select Ask AI and complete the conversation confirmation flow.

## Repository layout

```text
tradex-rag/                   Python API, MCP bridge, retrieval service and tests
knowledge_base/               Public sources and 28 curated bilingual policy cards
index.html                    Application shell
src/
  app.js                      Pages, navigation and order workflow
  knowledge.js                Uploads, retrieval chat and citation viewer
  data.js                     Bilingual copy and business templates
  finance.js                  Deterministic cash calculations
  partial-payment.js          Email-field clarification demo
  followups.js                Reminder and event-demo logic
  storage.js                  Browser state persistence
  icons.js                    Local SVG icons
  styles.css                  Base components
  clarity.css                 Finance-workspace layouts
  knowledge.css               Library and source-viewer styles
demo/                         Synthetic emails and financial records
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

`dist/`, `output/`, `previews/`, logs, process IDs, dependency folders, backend `var/` data, downloaded `.models/` and local credentials are excluded from Git. The repository includes source code, tests, synthetic examples, English setup documentation and public knowledge sources. Runtime databases and private uploads are created locally.

## State and deployment

Finance-demo state is stored in this browser under `tradex-workspace-v1`. Source files, indexed passages and document versions are stored by the backend in SQLite and Qdrant. Uploading a document does not itself modify financial balances; the order workflow requires field confirmation.

`dist/` contains static frontend assets. **GitHub Pages alone does not run the API proxy or Python backend.** For the connected application, run the Node server and RAG service together, or configure your hosting platform to forward `/api/*` and `/knowledge` to the backend. The current server binds to localhost; shared deployment needs an authenticated application boundary.

This directory is the repository root. Both services and the knowledge archive use paths relative to it; the surrounding desktop folders are not required.

### Deep Agents, public search and sandbox

TradeX now uses the open-source Deep Agents harness for its Coordinator and three business subagents. Human clarification, background task progress and cited answers use the same frontend workflow. See [agent setup](docs/AGENTS.md#local-setup) for the optional OpenSandbox service and public web search. Main model credentials remain in `tradex-rag/.env`; web search reuses `OPENROUTER_API_KEY`.

## Start a demonstration from zero

Run `npm run demo:empty` from the repository root after installing the frontend and backend dependencies and configuring `tradex-rag/.env`. Open http://127.0.0.1:5174/. This starts an isolated frontend and backend on ports 5174 and 18770. It creates a new tenant and data directory for each invocation, without changing the existing workspace on port 5173. Stop it with Ctrl+C before starting a new rehearsal. Keep the terminal open during the demo.

The first screen contains no orders, financial projections, chat history or uploaded documents. Upload each supplied Word record in `demo/baseline/` or choose **Read the sample file**, review its extracted fields, then confirm the import:

1. Company cash schedule: opening CNY balance and separate USD balance.
2. Sales order: TF-26104, outstanding USD 12,000 and expected receipt date.
3. Supplier terms: CNY 160,000 due on 22 October.

Choose **Build orders & cash dashboard** to reveal the initial CNY 32,000 shortfall. Then open Harbour Supplies, upload `demo/screenshot-case/buyer-email.png` in Documents, and select **Ask AI**. When asked, enter USD 6,000 and 29 October 2026. Leave the remaining USD 6,000 unscheduled, then confirm the proposed fields.

The baseline importer reads the supplied case's Word paragraphs and schedule tables with deterministic field extraction. It does not use an LLM or support arbitrary company datasets. The subsequent email analysis uses the configured agent service. The initial USD 19,970 belongs to other overseas commitments; a second customer order is not created from that balance. New sessions start without public-policy seeds; add policy documents separately when needed.

Each session is saved under `tradex-rag/var/empty-demos/`. Reopening the same printed URL retains the confirmed imports; restarting the command creates a fresh rehearsal.

## Email screenshot workflow

Upload a PNG, JPG or WEBP through **Documents**, link it to the order, and choose **Ask AI** after indexing. The backend sends the image directly to the configured vision model, stores the transcription and payment fields with the source version, and indexes them for retrieval. Missing amount or date fields remain empty until the assistant asks the user. Confirmation updates the expected receipt and cash projection, while the bank balance and total outstanding receivable remain unchanged. Citation buttons open the original screenshot alongside the extracted text.

Configure `TRADEX_MODEL_VISION` in `tradex-rag/.env`. It uses the existing provider and API key and defaults to `TRADEX_MODEL`. The tested OpenRouter configuration is `deepseek/deepseek-v4.1-flash`. Image extraction is cached per source version so an indexing retry can reuse the result. No separate OCR service is required.

The bell opens a contextual event list. Opening it marks the displayed events as read; the alerts remain available. Expand an event to inspect its cash impact, open its order or explicitly start AI analysis. Unchanged financial alerts retain their read state across unrelated workspace versions.
