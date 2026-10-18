# TradeX

An export-finance workspace for small Chinese trading businesses. TradeX connects company cash, order evidence, document search and an AI conversation in one workflow.

## Quick start

Requires **Node.js 20+**. The frontend has no third-party runtime dependencies.

```bash
npm run dev
```

Open **http://127.0.0.1:5173**. Reload the browser after editing source files.

```bash
npm run check              # JavaScript syntax checks
npm test                   # Payment and reminder logic tests
npm run build              # Copy deployable assets into dist/
npm run preview            # Serve dist/ with the same backend proxy
npm run check:integration  # Live RAG integration checks; both services required
```

Use `PORT=5174 npm run dev` to change the frontend port. Stop the development server before starting preview on the same port.

## Connect the knowledge service

The knowledge service is a separate Python application, `tradex-rag`, in the TradeX workspace. This frontend repository does not include its database, model weights or uploaded files.

Start the existing service in another terminal:

```bash
cd ../tradex-rag
./start.sh
```

The frontend server forwards `/api/*` to **http://127.0.0.1:8765**. The `/knowledge` page opens the bilingual library workbench through the same proxy. Set `TRADEX_RAG_PORT` when starting the frontend if the backend uses a different port:

```bash
TRADEX_RAG_PORT=8766 npm run dev
```

The finance demo can run independently. Upload, document retrieval and cited answers require the RAG service. A disconnected service is shown in the document library.

### Qwen configuration

Configure credentials **only in the backend**, in `tradex-rag/.env`:

```dotenv
TRADEX_EMBEDDING=bge-local
DASHSCOPE_API_KEY=your_model_studio_api_key
DASHSCOPE_BASE_URL=your_regional_openai_compatible_base_url
TRADEX_CHAT_ENABLED=1
TRADEX_CHAT_MODEL=qwen-plus
```

Copy the compatible API base URL from the same Alibaba Cloud Model Studio regional workspace as your key. It should end in `/compatible-mode/v1`; the backend appends `/chat/completions`. Restart the RAG service after changing `.env`.

- With `TRADEX_CHAT_ENABLED=0`, the assistant displays actual retrieved passages and source references. It makes no generation-model calls.
- With a configured key, endpoint and `TRADEX_CHAT_ENABLED=1`, the backend asks Qwen to answer using the retrieved evidence and validates the returned source IDs.
- Local BGE embeddings remain independent of the Qwen chat setting.

Never place an API key in `src/`, browser storage, a frontend environment variable or a GitHub commit. Both project `.gitignore` files exclude `.env` files.

Official interface reference: [Alibaba Cloud Model Studio — OpenAI-compatible Chat API](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions).

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

The file is synthetic: it describes a USD 6,000 payment promise for 29 October 2026 and an unscheduled USD 6,000 remainder. Retrieval does not turn that promise into a confirmed bank receipt.

### Partial-payment clarification demo

The order workflow also contains a local field-confirmation demo. Select Harbour Supplies and use `demo/buyer-partial-payment.txt` or the sample button. Its email omits the amount and date; the local parser requests those fields before confirmation. Replies such as “6000美元” and “10月29日” complete the draft. Confirmation updates the demo order and cash projection. This workflow remains separate from general document retrieval and Qwen-generated answers.

## Repository layout

```text
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

`dist/`, `output/`, `previews/`, logs, process IDs, dependency folders and local credentials are excluded from Git. The GitHub-ready ZIP contains only source, tests, synthetic examples and documentation.

## State and deployment

Finance-demo state is stored in this browser under `tradex-workspace-v1`. Source files, indexed passages and document versions are stored by the backend in SQLite and Qdrant. Uploading a document does not itself modify financial balances; the order workflow requires field confirmation.

`dist/` contains static frontend assets. **GitHub Pages alone does not run the API proxy or Python backend.** For the connected application, run the Node server and RAG service together, or configure your hosting platform to forward `/api/*` and `/knowledge` to the backend. The current server binds to localhost; shared deployment needs an authenticated application boundary.

When creating a repository, select this `tradex-frontend` folder or use the clean ZIP. The surrounding desktop and parent folders are not part of this project.
