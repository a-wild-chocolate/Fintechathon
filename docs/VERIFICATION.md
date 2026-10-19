# Verification record

Checked locally on 18 October 2026.

## Automated checks

- Frontend JavaScript syntax: passed.
- Frontend business-logic tests: 10 passed.
- RAG backend tests: 22 passed, including source-version preservation, order/tenant isolation, unknown model citation rejection and a mocked Qwen response.
- Live integration through the frontend proxy: passed for multipart upload, background indexing, English and Chinese retrieval, version-specific original downloads, order filtering and English policy metadata. Temporary integration documents are archived after the check.
- Static production build: passed.

## Browser checks

- English → Chinese switching updates the document interface and assistant controls.
- Public policy display titles switch between Chinese and English.
- The document list refreshes after a backend upload and shows the indexed document as searchable.
- **Ask AI** beside the uploaded document carries its document and order scope into the conversation.
- English and Chinese questions return source passages with numbered references.
- Citation buttons open the correct file version and source passage; the original-download link points to that version.
- The standalone library switches to English and runs its English DDP example query.

The browser extension could not assign local files without its file-URL permission. Multipart upload was verified through the same frontend proxy endpoint; the native file-picker automation was not completed. This restriction affects automated file selection, not the application's normal file-input control.

For automated Chrome file selection: To enable file upload, open chrome://extensions, click Details under the ChatGPT browser extension, and enable "Allow access to file URLs." See [here](https://developers.openai.com/codex/app/chrome-extension#upload-files) for details. Manual uploads do not require this automation permission.

## Model setup

No paid Qwen calls were made. The live preview uses local BGE retrieval and explicitly labeled source excerpts. Qwen response handling was tested with a mocked provider. Configure `tradex-rag/.env` and enable chat to validate your chosen regional model endpoint.

## Original frontend-only package (18 October)

Only the frontend source, English documentation, tests and synthetic demo records are included. The separate RAG backend, local database, uploaded files, embedding weights, API keys, logs, screenshots and `dist/` output are excluded.

## Integrated repository (19 October)

The repository now includes `tradex-rag/` backend source and `knowledge_base/` public materials. The original frontend-only ZIP is superseded by this repository layout. Runtime databases, private uploads, model weights, virtual environments and credentials remain excluded. See the root and backend READMEs for a fresh-clone setup.

Checks repeated against the integrated repository:

- Frontend syntax, 10 business-logic tests and production build: passed.
- Backend tests imported from the new repository path: 21 passed, one optional tokenizer check skipped because this source checkout has no bundled model weights.
- Fresh temporary SQLite/Qdrant library using the existing local BGE cache: all 28 public cards indexed; repeat seeding added zero duplicates; every card retained an English title; English and Chinese hybrid retrieval returned results. No paid API calls were made.
- Knowledge archive: all 28 card references and 10 keyword fixtures passed after rebuilding.
- Git exclusions checked for credentials, Python environment, model weights, runtime database, uploads and bytecode.

Browser interaction checks above remain the 18 October record; this packaging update did not repeat them.

## Fresh GitHub clone verification (19 October 2026)

The published `main` commit `0736bf9` was cloned from GitHub into an independent temporary directory. Verification used a newly created Python 3.12 virtual environment and Node.js 20.20.2 on macOS. Existing project databases, uploaded files, virtual environments and model directories were not copied into this clone.

| Step | Observed result |
| --- | --- |
| Install with `pip install -e '.[test]'` | Succeeded; `pip check` reported no broken requirements |
| Run `scripts/download_model.py` | Downloaded public BGE files to the clone's own cache; verified 512-dimensional output |
| Run `cli seed`, then `cli drain` | 28 documents ready, 28 chunks embedded in local SQLite/Qdrant |
| Backend tests after model download | 22 passed, including the actual local tokenizer check |
| Frontend syntax, unit tests and production build | Passed; 10 unit tests |
| Public knowledge validation | 28 card references checked; 10/10 keyword fixtures passed |
| Start backend with `start.sh` and frontend with `npm run dev` | Both started successfully on alternate ports 18765 and 15173 |
| Live integration through the frontend proxy | Upload, background indexing, Chinese/English answers, versioned original downloads, order isolation and English policy titles passed |

The current integration script also requires at least one public policy, so an unseeded library can no longer pass the title check vacuously; that change was checked against the same fresh-clone services. The temporary servers were stopped after verification.

A tokenizer test was initially launched while the model download was still in progress and failed on the incomplete cache; after the download finished, all 22 backend tests passed. Follow the documented sequence and finish the model download before indexing or running that test.

Qwen requests were not sent. The default backend configuration uses cited excerpts without an API key. Real generated answers require the user's Model Studio key, regional base URL and chat switch in `tradex-rag/.env`. Native Windows and Linux were not exercised in this macOS check; Windows instructions use WSL2. Browser visual checks remain the earlier record above.

## Main/subagent integration (19 October 2026)

- Backend suite: 29 passed, one optional local-tokenizer test skipped because this checkout has no model cache; the socket integration test is selected separately.
- Real HTTP + stdio MCP + LangGraph integration: one passed. Covered three clarification turns, explicit confirmation, cash recalculation, decision drafting, original-source download and persisted run state.
- Frontend syntax, 10 business-logic tests and static build passed; `pip check` found no broken requirements.
- Isolated browser check on ports 15174/18766: selected an order-linked email through **Ask AI**, supplied USD 6,000 and 29 October, confirmed the proposal and observed automatic reanalysis. Reload retained the new forecast: CNY 128,000 cash, CNY 34,000 peak shortfall, USD 6,000 scheduled and USD 6,000 unscheduled. English/Chinese controls and the version-specific source dialog worked.
- A duplicate **New chat** control found during this check was removed; the existing button now clears the current order's session bindings as well as its visible conversation.

Model responses and embeddings in these agent checks were deterministic test fixtures. The orchestration, MCP transport, workflow services, SQLite persistence and frontend were real. No paid OpenRouter, Qwen or DeepSeek request was sent. Provider payloads were tested with mocked HTTP transports; live tool selection and answer quality remain to be checked with a configured key. Existing security experiment files were not changed.

## Live OpenRouter startup (19 October 2026)

Started the repository backend on port 8765 and verified the existing frontend proxy on 5173. Copied the stopped legacy backend's local model cache and runtime library into the repository's ignored runtime directories; all 32 documents and 41 embedded chunks were retained. Credentials were not copied from the legacy backend.

The first live request reached OpenRouter but failed after 17 calls because ordinary assistant text did not satisfy the structured completion contract and subsequent delegations exhausted their budgets. The OpenRouter adapter now requires tool calls; the last allowed role call offers only `finish`, and prompts describe exact delegation and finalization. Regression checks passed: 31 backend tests, plus the separate real HTTP/MCP integration test.

One fresh post-fix request completed through Coordinator, Cash-flow and Decision, with 14 model calls and no tool errors. Current cash shortfall was CNY 32,000; a conditional ten-day supplier extension removed the modeled shortfall. Provider-reported inference costs were USD 0.00404184 for the failed request and USD 0.00476214 for the completed request. These are observed costs for these two requests, not a general per-task estimate.

This check did not exercise live Reconciliation or upload clarification. Existing library fixtures contain inconsistent historical amounts (a CNY 72,000 supplier record versus CNY 160,000 in the current demo schedule, plus a separate USD 6,000 payment promise). The successful execution demonstrates transport and orchestration; the demo fixtures still need alignment before a coherent end-to-end business presentation. No payment plan was committed by these checks.

## Live progress UI (19 October 2026)

Added asynchronous run creation, a progress endpoint and timestamped model/tool start events. The frontend now shows the current specialist, actual operation and completed steps, with English/Chinese labels and a retained activity record.

Checks: 31 backend tests passed; two real HTTP/MCP integration tests passed, including a deliberately paused model proving that progress is available before completion; 14 frontend tests passed, including delegation status, failure labels and one-POST/poll-only transport. Browser testing with a delayed model fixture showed Coordinator → Reconciliation transitions, document-read and field-preparation operations, language switching and preservation of unsent input. No paid model call was made for this change.

## Background task continuity and call-budget fix (19 October 2026)

Three failed local runs completed their specialist work but exhausted the 18-call budget before the Coordinator could summarize. The runtime now reserves a final Coordinator call and retains completed specialist output if a later step fails.

The browser previously changed all saved pending requests into errors during startup. Saved run IDs now reconnect to their existing backend execution. New conversations archive visible turns without removing live tasks, and the global task panel restores the corresponding order/document context. Session updates from an old background task cannot overwrite a new conversation binding.

- Backend unit suite: 33 passed, two socket integration tests deselected.
- Real HTTP, LangGraph and stdio MCP integration: two passed with fixture model responses.
- Browser on isolated ports 15176/18766: started an order-linked task, navigated to the company dashboard, reloaded while running, reopened the task and started a new chat. The original task completed in the background; its unread-result entry restored the order conversation and source citation.
- Frontend syntax checks, 18 unit tests and static production build: passed.
- New regression cases cover reload recovery, archived running tasks, unread-history retention, conversation session isolation, final Coordinator capacity and partial-result preservation.

The browser fixture delays model responses to exercise navigation during execution. These checks made no paid API requests.

## Structured human clarification (19 October 2026)

- Backend unit suite: 36 passed, two socket tests deselected.
- HTTP + real stdio MCP integration: two passed, including structured answer submission, duplicate submission returning the same continuation, original conversation identity, and separate proposal confirmation.
- Frontend syntax and 21 unit tests passed. New cases cover no preselected options, free-text-only answers, skipping with a note, saved drafts, and escaped display text.
- Isolated browser fixture on 15177/18767: selected the supplier-payment interpretation, entered a note, navigated away and reloaded, restored both fields, then submitted and observed a Cash-flow subagent continuation. Waiting for a human incurred no fixture model calls. A separate English conversation exercised Skip all; it continued with the payment direction unknown and the cash schedule unchanged.

The fixture supplies model responses; HTTP, MCP, orchestration, storage and frontend controls are real. No paid model request was made. Deep Agents migration, sandbox execution and live web search remain design recommendations and were not activated by this change.

## Deep Agents migration — 19 October 2026

- Replaced the custom LangGraph model/tool loop with Deep Agents 0.7.28 and native `task` delegation. The replaceable provider transport and MCP business tools remain in use.
- Backend regression suite: 36 existing unit tests passed; three new extension tests cover public-source filtering, redirect handling and sandbox input/cleanup.
- Real HTTP + stdio MCP + Deep Agents: two integration tests passed, covering human replies, confirmation, finance workflows, citations and live progress.
- Frontend: 21 tests, syntax validation and build passed.
- Real OpenSandbox execution passed: decimal total 10000, UID 65534, no provider keys in the container, and blocked connection to an external IP. The container was destroyed after execution. SDK file modes use permission digits (444); the pinned execd image accepts a fixed command string.
- Browser verification with fixture model responses: English clarification choices and notes continued into the cash-flow specialist; navigating to Overview while it ran preserved the completed answer and activity log.
- Browser citation verification: a web citation opened its saved excerpt, retrieval timestamp and external source link without a library lookup.
- OpenRouter web transport was tested with fixture responses; no paid search or model request was made in this migration verification. Live search quality and account/provider availability have not been measured.

The migrated preview also passed Chinese/English interface switching.

Live public-page retrieval also succeeded against UK government import guidance (6,641 characters); this did not invoke a search model.


## Agent continuation repair — 19 October 2026

The failed run `8281e114-a2c0-42e2-bccd-2ff9873d9950` ended after a model response used all 1,800 output tokens. The old trace retained only a generic exception category, so truncation is a strong diagnostic indication, not a recovered provider termination reason.

The transport now records provider termination reasons, uses a configurable 4,096-token output cap, and distinguishes truncation, malformed tool arguments, missing results and result validation failures. The cash specialist receives calculation tools and compact financial results; earlier generated prose is excluded from its financial context. Source identifiers remain available for retrieval and citations.

Verification: 44 backend tests, 2 HTTP/MCP integration tests with scripted responses, and 24 frontend tests passed. Live OpenRouter run `e29a8fe5-f323-4f1e-a480-258ac647ebd2` completed using the same submitted clarification answers. Its supplier date, receipt date, receipt amount, supplier amount and peak shortfall matched the calculation result. The earlier live verification completed but reused stale financial figures, which prompted the context repair. A further instruction distinguishes a funded scenario from a risk-free shipment; the final narrowing of cash-agent tools and this wording were not given another paid inference run. Existing failed records remain unchanged.
