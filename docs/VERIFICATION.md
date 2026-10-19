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


### Selective clarification continuation — 19 October 2026

- Persisted specialist outputs, compact workflow facts and source-version dependencies in run results.
- Added a Coordinator continuation plan and displayed reused specialists in activity.
- Real Deep Agents tests with a scripted provider cover preference-only continuation, cash-scenario changes, evidence updates, acknowledgements, source citations and runtime restart. The preference fixture invokes only Decision; the acknowledgement fixture invokes no subagent. These are execution-path checks, not measured live-provider speed improvements.
- Backend suite: 51 passed (2 integration tests selected separately). Frontend suite: 32 passed; syntax checks and build passed.
- HTTP + stdio MCP integration: 2 passed using the scripted provider. Local backend restarted successfully after confirming no running agent tasks. No paid-provider latency benchmark was run for this change.

### Real-model clarification replay — 19 October 2026

Used the configured OpenRouter `qwen/qwen3-30b-a3b-instruct-2507` for a synthetic order through the real HTTP API, Deep Agents harness and stdio MCP tools. A separate tenant and SQLite/Qdrant directory protected the normal demo workspace. Embeddings were disabled for this routing test; document reads and lexical retrieval remained available. Web and sandbox tools retained the configured availability.

The case asks for a cash analysis, then a choice between buyer collection and supplier negotiation. The reply selects a buyer collection draft, confirms unchanged amounts/dates, and skips the supplier-extension question. Both revised continuations replay the same saved initial analysis and identical answers; the initial model run was not regenerated.

| Stage | Elapsed | Model requests started | Roles with returned model calls | Outcome |
| --- | ---: | ---: | --- | --- |
| Initial analysis | 286.9 s | 18 | Coordinator 6; Cash flow 5; Decision 7 | Asked clarification |
| Original continuation | 167.4 s | 13 | Coordinator 3; Cash flow 5; Decision 4 | Final Coordinator request timed out |
| Calculation-reuse correction | 68.3 s | 7 | Coordinator 3; Decision 4 | Draft saved; unsupported approval label and stale conversion remained |
| Final continuation | 74.7 s | 9 | Coordinator 5; Decision 4 | Completed; draft saved; no further questions |

The initial cash specialist finished its calculations but marked itself `needs_information` because it also asked an action preference. Result-only caching therefore missed valid calculations, and the original continuation repeated five cash-model calls. The scheduler now compares explicitly requested scenarios with saved calculations independently of narrative completion status. It also excludes stale cash/advice prose from the continuation context when authoritative calculations are available. An approval status must correspond to a pending workflow proposal.

Final assertions passed: only the Decision specialist started; the cash and reconciliation models received zero calls; saved cash calculations were reused; the workspace remained unchanged; a buyer collection draft was saved without sending; the final response reported CNY 32,000 on 22 October and the planned USD 12,000 receipt on 29 October without the earlier unsupported USD conversion. The final run has status `completed` and no questions.

This is a single-case observation, not an average speedup benchmark: the original continuation includes a model timeout, while the revised continuations complete. The final run still takes about 75 seconds and performs extra status, calculation and retrieval calls; eliminating specialist reruns does not eliminate provider latency or all unnecessary tool selection. Provider-reported inference charges across these four stages total USD 0.02968431; the timed-out request's unreported charge and any separate search/sandbox charges are excluded.

Regression verification: 54 backend tests passed, two real HTTP/MCP integration tests passed with fixture model responses, and 33 frontend tests plus syntax/build checks passed. A further workspace-version regression checks invalidation when only the calculation, rather than a completed cash-agent result, survives. Local raw traces and timing summaries are under ignored `tradex-rag/var/hitl-live-20261019/`; no credentials are included.


### DeepSeek model switch and bounded continuation — 19 October 2026

OpenRouter's public catalogue and endpoint listing include `deepseek/deepseek-v4.1-flash` with tool calling and structured output. The local default and all four role assignments use this model through the existing OpenRouter key. Reasoning is disabled for the interactive path; the provider adapter remains replaceable.

The Coordinator now selects the continuation once and the scheduler invokes only affected specialists. The final specialist response goes directly to the user. Read-only workflow results reuse normalized arguments and unchanged workspace/proposal state. An explicit draft task requires a draft in its completion schema, and completion is serialized so duplicate model calls cannot create two artifacts. DeepSeek finalization with only `finish` available uses schema-shaped JSON, converted to the same locally validated completion envelope. Normal business analysis retains tool selection.

The following development attempts replay the same synthetic initial checkpoint and identical human answers described above. Each attempt has a separate saved run; none silently replaced a failed record. The initial checkpoint was produced by Qwen, so this measures continuation rather than a complete DeepSeek analysis from upload.

| Attempt | End-to-end elapsed | Model requests started | Observed outcome |
| --- | ---: | ---: | --- |
| `optimized-qwen` | 25.9 s | 1 | Qwen; draft omitted |
| `optimized-deepseek` | 16.9 s | 3 | DeepSeek; two draft writes |
| `optimized-deepseek-final` | 30.0 s | 2 | Single save entry; output truncated |
| `optimized-deepseek-draft` | 14.8 s | 2 | Draft-only routing; duplicate completion saved twice |
| `optimized-deepseek-once` | 9.8 s | 2 | Serialized completion; one draft, incomplete deadline wording |
| `optimized-deepseek-repeat` | 30.1 s | 2 | Repeated case; output truncated |
| `optimized-deepseek-single-tool` | 3.1 s | 1 | Unsupported parallel-tool parameter; HTTP 404 |
| `optimized-deepseek-structured` | 40.8 s | 3 | Structured routing omitted draft mode; output truncated |
| `optimized-deepseek-final-json` | 35.8 s | 2 | Native routing omitted draft mode; output truncated |
| `optimized-deepseek-explicit-route` | 9.2 s | 2 | Required draft mode; model omitted optional draft |
| `optimized-deepseek-required-draft` | 13.9 s | 2 | Required draft result; one saved draft |
| `optimized-deepseek-verified-repeat` | 9.8 s | 2 | Unchanged configuration repeat; one saved draft |

The final unchanged configuration completed twice in 13.9 and 9.8 seconds, compared with the previous 74.7-second Qwen continuation. Each used one Coordinator and one Decision call, reused the cash calculation, saved exactly one draft, returned no new questions and preserved the financial workspace. No status, cash-calculation, comparison or retrieval tool was re-executed. Both responses retained the CNY 32,000 shortfall on 22 October and the existing USD 12,000 receipt schedule. This comparison changes both orchestration and model; it does not isolate a model-only speedup or estimate typical latency across cases.

Artifact review found remaining writing-quality issues: the final two saved email bodies contain literal `%0A` separators, mention internal cash pressure, and ask for payment before 29 October without clearly requesting availability by the 22 October supplier deadline. They were saved as drafts, never sent. Execution and latency assertions pass; polished correspondence quality is not a passed criterion. Earlier completed-status runs that omitted or duplicated drafts are not counted as successful functional checks.

Provider-reported inference charges across these development attempts total USD 0.01095045; the rejected parameter request reported no usage. The unsupported `parallel_tool_calls=false` setting was removed. No automatic retry or alternate-provider fallback was introduced. Local traces and synthetic model outputs remain under ignored `tradex-rag/var/hitl-live-20261019/`.

Final regression checks: 59 backend unit tests and two real HTTP/MCP integration tests passed; integration model responses were scripted. The frontend was unchanged by this model switch. After confirming zero active runs, the local backend restarted; both port 8765 and the port 5173 frontend proxy reported OpenRouter DeepSeek V4.1 Flash for all four roles.

### Conversation presentation — 19 October 2026

The AI page now uses a centered reading column, soft user bubbles, an unboxed assistant response and a sticky composer. The actual agent operation is a compact expandable activity row; its indicator and existing list rows persist across polling updates. A completed reply replaces only its own message instead of rerendering the entire page. New replies use a brief fade/translation, with reduced-motion support, rather than simulated token streaming. Readers away from the conversation end are not automatically pulled down.

The input grows with its content; Enter sends and Shift+Enter inserts a newline. IME composition does not submit, and sending is disabled while the current conversation runs, while draft editing remains available.

Verification used the real page at port 5173 and a separate UI fixture with scripted execution events, without paid model calls or changes to business data. Browser checks confirmed preserved activity disclosure, indicator and row DOM nodes, and preserved unsent input, focus and selection when a response arrives. English/Chinese controls, Enter submission and Shift+Enter multiline editing passed. The actual page was visually checked at a narrow viewport and the conversation fixture at desktop width. Frontend syntax, 35 tests and build passed.

### Scrollable conversation panel — 19 October 2026

The assistant keeps all active conversation turns in chronological order inside a viewport-sized scroll region; earlier turns are no longer folded into a separate disclosure or removed by the archived-history retention limit. Navigation and the composer remain outside the scrolling message area. Reply completion preserves the reading position when the user has scrolled up, and language changes restore the same scroll offset.

Verification: 36 frontend tests, JavaScript syntax checks, and production build passed. The browser fixture confirmed nine retained replies, independent panel scrolling, stable composer placement, and preserved reading position after a scripted completion. The live order conversation was checked at a 598 px viewport, including scrolling to earlier messages and switching Chinese/English without losing the reading position. No model calls were needed for these presentation checks.

### Screenshot payment evidence and notification inbox — 19 October 2026

A real OpenRouter DeepSeek V4.1 Flash run used `demo/screenshot-case/buyer-email.png` through the browser upload flow in an isolated workspace on ports 5176/8766. The image contained a partial-payment promise but no amount or payment date. Extraction returned null for both fields, correctly leaving the email header date separate. The source viewer displayed the uploaded image and cited extracted fields in Chinese and English controls. The model misread the small demonstration footer brand; payment-field checks passed, not verbatim transcription accuracy.

The assistant requested the missing amount and date. The user supplied USD 6,000 and 29 October 2026 and left the residual balance unscheduled. The 26.4-second clarification continuation invoked only Coordinator and Reconciliation. The financial workspace remained at version 1 until explicit confirmation. Confirmation produced version 2, expected CNY 40,000 on 29 October, unchanged opening CNY 128,000 and outstanding USD 12,000. The first gap remained CNY 32,000 on 22 October and the peak became CNY 34,000 on 6 November. Subsequent Coordinator, Cash-flow and Decision execution completed and generated action advice and a saved draft. No message was sent. This was one synthetic case, not a latency benchmark.

The notification browser check confirmed that opening the inbox removed the badge, reloading retained the read state, event details exposed impact and next action, and View order navigated to TF-26104. Chinese and English labels were checked. Stable event identities prevent unrelated version changes from regenerating unread cash alerts.

Three baseline Word documents were reformatted as single-page business records, rendered and visually checked. Their actual extracted text passes the deterministic onboarding checks. Frontend syntax, 39 tests and production build passed. Earlier backend verification in this change passed 63 unit tests with 2 integration tests deselected; image tests check the real image payload shape, null fields, extraction cache reuse and source-image access using a scripted model.

### AI task result navigation — 19 October 2026

Selecting an AI task now opens its scope and document context, restores linked clarification turns, marks that result read, and moves focus and panel scroll to its answer after normal scroll restoration. The selected answer has a brief left-edge highlight. Unread tasks remain reachable even when older than the eight recent entries; completed entries distinguish New result from Viewed.

Browser verification selected the earliest and latest real saved screenshot-analysis tasks in the isolated workspace. Both different answers received focus and appeared 24 px below the conversation panel top. A scripted nine-reply fixture independently checked targeting an older reply. No model calls were made. JavaScript checks, all 40 frontend tests and the production build passed.


## Relational business persistence — 19 October 2026

Added company, counterparty, account, order, cash-movement, evidence-reference and financial-revision tables in `agents.sqlite3`, plus server-backed workspace views. Existing forecast snapshots migrate once. Model-confirmed payment promises update the expected cash movement transactionally without changing actual opening balances or settled order value. Frontend startup restores server state before using the local cache.

Validation: 69 backend tests passed (2 opt-in tests deselected); 41 frontend tests passed; JavaScript syntax checks and production build passed. API tests reopen the database through a fresh application, and browser verification at a distinct origin recovered the existing CNY 128,000 balance, USD 6,000 promise, CNY 34,000 peak gap and three AI turns. No paid inference was required for these persistence checks.

## Company and order management — 19 October 2026

The default application now opens a company selector. New companies start with dated CNY/USD balances and an empty order ledger. Company creation and order create/edit use a review-and-confirm flow; order previews roll back their SQL transaction, while confirmation saves the order, counterparties, payment terms, cash movements and financial revision together.

Verification in an isolated local database:

- Created `Pearl Export QA` in the browser with CNY 50,000 and USD 2,000, then created EUR order `PE-901` for a new customer. No sample orders were copied.
- With a CNY 70,000 supplier payment on 5 November and a EUR 5,000 expected receipt at 8 CNY/EUR on 15 November, the preview and saved dashboard showed a CNY 20,000 gap.
- Edited the supplier payment to CNY 30,000. The preview and confirmed dashboard changed the gap to zero without adding duplicate movements. Reloading the browser and restarting the backend retained the company, order and balances.
- Used the configured OpenRouter model on this saved order. The first live answer exposed integer cents as yuan; model-facing workflow and context serializers now consistently expose major currency units. The subsequent completed run (`cb41e1f9-f9f2-4e7a-b0af-4985a7fb9f19`) used CNY 50,000 opening cash, CNY 30,000 supplier payment, EUR 5,000 / CNY 40,000 expected receipt, CNY 0 shortfall and EUR 3,000 unscheduled balance. The page was changed to Overview while analysis continued.
- Checked English/Chinese dashboard labels, the dynamic order selection in document upload and the original company's separate entry in the company selector. Uploaded a synthetic payment text through the browser, observed `Ready for AI`, then verified that **Ask AI** carried both `PE-901` and the uploaded document into the composer.
- Backend suite: 74 passed, 2 socket integration tests deselected. Two additional currency-clarification and preserved-adjustment cases were then added; the focused company suite passed all 7 cases.
- Frontend: 42 tests passed, including a new saved-company chart case with independent dates, amounts and order IDs; syntax validation and production build passed.

The company API tests cover preview rollback, confirmed persistence, edits, cancellation, version conflicts, invalid amounts, duplicate order numbers, company isolation, MCP run routing, document scope, currency units and idempotent receipt confirmation. The current order editor supports one next expected receipt and one supplier payment per order; opening balances include historical receipts rather than posting them again.

## New-company screenshot-to-cash verification — 19 October 2026

Created a separate synthetic company, **Cedar Export QA**, and order **CW-GB-112** through the normal browser review/confirmation flow on ports 5173/8765. This case deliberately uses GBP and November dates instead of the legacy USD/October demonstration. Company ID: `c09d22c4-72cb-48a1-b552-1ab4a762e2bf`.

### Saved records and expected result

- Opening availability: CNY 42,000 and a separate USD 1,000 account as of 1 November 2026.
- Northbridge Home order: GBP 18,000 total, GBP 3,000 already received, GBP 15,000 outstanding; rate assumption 9.2 CNY/GBP.
- Original forecast: GBP 15,000 available 7 November; CNY 95,000 payable to Foshan Cedar Lighting on 9 November. This forecast has no shortfall.
- Uploaded a synthetic buyer email screenshot stating partial payment without an amount or payment date. The email header is dated 3 November 2026 and is not a receipt date.
- First clarification supplied only GBP 4,000. The next clarification asked only for the missing date; then supplied 16 November 2026. The company remained at financial version 2 and the original order terms remained unchanged until the confirmation button was clicked.
- Confirmation advanced the company to version 3 and replaced its expected receipt with GBP 4,000 / CNY 36,800 on 16 November. The first and peak CNY gap is **53,000 on 9 November**, reducing to **16,200 on 16 November**. GBP 11,000 remains unscheduled. Opening balances and the GBP 3,000 already received are unchanged.
- Direct SQLite inspection verified one supplier movement and one expected receipt, the revised order terms, and a version-specific evidence link to the uploaded screenshot. The original `demo-exporter` remained at version 6. Browser refresh retained the new records and chart; changing pages did not interrupt analysis. English/Chinese labels and the source viewer were checked.

### Real-model findings and repairs

The initial DeepSeek image extraction misread parts of the header, including the year, although it correctly left the payment amount/date null. A Qwen image check read the header and body correctly on this screenshot. The local configuration and documented OpenRouter vision default now use `qwen/qwen3.5-plus-20260420`; conversational agents remain on DeepSeek V4.1 Flash. New document `d02180e0-72cc-4309-a600-710c0df823ce` preserves the corrected extraction. Existing source versions and unsuccessful execution records were retained.

The second HITL continuation exposed omitted tool arguments: the model repeatedly left out the supplied date and mentioned an irrelevant USD amount. The agent-facing receipt contract now requires explicit amount, currency, date and evidence IDs, with nullable unknowns; the legacy USD-only alias remains available to the underlying MCP service but is removed from the agent-facing schema. Duplicate receipt proposals within one turn reuse their result. Missing-field cards take their fields from the proposal, and generic currency amount changes invalidate reconciliation dependencies. The repaired continuation (`ca295358-ee77-449f-a820-a7f0dbb54a21`) completed in **7.9 seconds**, using three model calls across Coordinator and Reconciliation, retaining GBP 4,000, 16 November and both source references. This is an individual development measurement.

Post-confirmation analysis correctly calculated the CNY 53,000 gap but encountered scenario errors and produced a poor unsolicited draft. Tool errors now retain their actionable business explanation; prompts distinguish confirmed state from an unconfirmed proposal and request residual-gap checks before recommending a timing change. A subsequent real run (`076a3995-42e3-44e0-a7fb-0f97066afa64`, 36.0 seconds) calculated the current plan and both alternatives with no tool errors: receipt on 6 November leaves CNY 16,200 short on 9 November; supplier payment on 17 November leaves CNY 16,200 short on 17 November. No draft or financial change was made. One generated sentence still called this a timing rather than amount problem despite correctly reporting the residual funding need; narrative consistency is not a fully passed criterion.

### Demo-data boundary

The normal company UI and managed-company financial tools read company-scoped SQL records, dates, currencies and orders. No legacy order IDs or financial constants appeared in the new company's saved ledger or calculations. The old `?demo` / `?setup` route, legacy workflow branch, fixtures and demonstration documents still contain intentional sample data; they have not been deleted. The initial HTML now keeps that legacy layout in an inert template so it does not flash sample company information while a normal workspace loads.

Local proof files are under ignored `output/screenshot-flow/`: the input image, source citation screenshot, confirmation screenshot, dashboard screenshot, SQL snapshot and model run summary. They contain synthetic data. No email was sent, no payment was executed, and no Git commit or push was made during this verification.

Final regression results for this verification: **80 backend tests passed** (2 opt-in socket integration tests deselected); **42 frontend tests passed**, with JavaScript syntax validation and production build passing. The browser flow above exercised the live HTTP/MCP/model path separately from the scripted unit tests.
