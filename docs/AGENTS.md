# TradeX main agent and subagents

The product uses a Coordinator with three business subagents. This implementation is independent of `hackathon_guard_mvp/`; it does not load security experiment workers, policies or checkpoints.

## Execution path

Browser conversation → `/api/assistant/runs` → Coordinator → selected subagents → MCP business workflows → shared evidence and forecast state → cited response or confirmation card.

[Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) owns the model/tool loop and native `task` delegation. TradeX supplies a small provider adapter, role-specific MCP tools, call budgets and public activity events. The Coordinator invokes three business subagents with separate contexts and combines their results. Dependent subagent invocations are serialized; no additional general-purpose worker is created.

| Role | Responsibility | Business tools |
| --- | --- | --- |
| Coordinator | Understand the request, delegate, combine questions and explain the result | `wf_status`, `kb_search`, `evidence_read` |
| Reconciliation | Read evidence, identify missing payment fields and prepare a receipt proposal | Shared read tools plus `wf_reconcile` |
| Cash flow | Translate hypotheses into parameters and explain calculated balances | `wf_status`, `kb_search`, `wf_cash` |
| Decision | Compare conditional responses, retrieve financing requirements and save drafts | Shared read tools plus `wf_cash`, `wf_options`, `wf_financing`, `wf_draft` |

`finish` returns a structured role result. `task` is the harness delegation tool and `finish` is the structured business result tool; financial and knowledge operations are MCP tools. The existing document upload, version and write-lease MCP tools remain available to external clients. The core roles use the tools listed above; optional public-search and sandbox tools are described below.

## Provider configuration

Set the following in `tradex-rag/.env`, then restart `./start.sh`:

```dotenv
TRADEX_AGENTS_ENABLED=1
TRADEX_MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
TRADEX_MODEL=qwen/qwen3-30b-a3b-instruct-2507
TRADEX_MODEL_CONCURRENCY=2
TRADEX_AGENT_MAX_CALLS=18
TRADEX_CHAT_ENABLED=0
```

These settings enable all four roles with one API key and model. To assign different models, set `TRADEX_MODEL_COORDINATOR`, `TRADEX_MODEL_RECONCILIATION`, `TRADEX_MODEL_CASH_FLOW` and `TRADEX_MODEL_DECISION`. OpenRouter's public model catalogue listed tool support for `qwen/qwen3-30b-a3b-instruct-2507` and `deepseek/deepseek-v3.2` when checked on 19 October 2026. These are starting configurations, not a measured ranking.

The provider adapter owns credentials, endpoints, role model assignments, request parameters, concurrency and usage metadata. Provider failures are recorded without automatic retry or cross-provider fallback. The OpenRouter adapter requires support for the requested parameters and disables provider fallback for that request. The two-request concurrency setting is an application budget, not a claimed OpenRouter limit.

Direct-provider alternatives use the same agent and workflow code:

| Provider | Key variable | Base URL | Model example |
| --- | --- | --- | --- |
| `openrouter` | `OPENROUTER_API_KEY` | Defaults to `https://openrouter.ai/api/v1` | `qwen/qwen3-30b-a3b-instruct-2507` |
| `qwen` | `DASHSCOPE_API_KEY` | Set `DASHSCOPE_BASE_URL` to the workspace's regional compatible endpoint | `qwen-plus` |
| `deepseek` | `DEEPSEEK_API_KEY` | Defaults to `https://api.deepseek.com` | `deepseek-chat` |

When changing provider, change `TRADEX_MODEL` and any role overrides to that provider's model IDs. `TRADEX_MODEL_BASE_URL` is an optional explicit override; clear it when switching providers unless needed. Credentials and `.env` remain backend-only. `/api/agents/status` reports configuration without exposing keys; `multi_agent` means configured, not a completed provider-call test.

## Clarification and confirmation

1. Upload an email and link it to `TF-26104`; wait until it is searchable, then select **Ask AI**.
2. The Coordinator delegates document interpretation to Reconciliation. Missing amount/date fields are persisted as a proposal with `needs_information` status.
3. Replies use the same `session_id`. Known fields and previous questions survive browser reloads and completed-turn server restarts.
4. A complete proposal becomes `needs_approval`. The conversation displays its amount/date and a **Confirm and update dashboard** button.
5. The confirmation endpoint checks the proposal's source and financial versions, updates the expected receipt schedule and returns a new workspace version. Repeated confirmation returns the same result.
6. The frontend updates its order and cash views, then asks the Coordinator for new cash analysis and action suggestions.

Only explicit UI confirmation changes accepted forecast fields. The model cannot invoke that endpoint through its tool list. Receipt promises never change actual bank cash. Changed sources or state require reanalysis before confirmation.

The current financial workflow uses the existing synthetic company schedule: CNY 128,000 opening cash by default, USD 12,000 expected order balance, CNY 160,000 supplier payment and the same additional company flows as `src/finance.js`. Amounts and dates confirmed in the browser override the initial forecast. USD conversion uses the demo ratio of CNY 80,000 per USD 12,000 and is labeled as an assumption. Partial receipts replace the original forecast, leaving the remainder unscheduled. Other orders support evidence questions but need a financial schedule before these tools can calculate their cash impact.

## Shared state and persistence

The evidence library remains in `var/library.sqlite3` with Qdrant vectors and immutable files. `var/agents.sqlite3` stores conversation turns, runs, public tool activity, source references, proposals, drafts and the latest demo forecast. Both are excluded from Git.

The frontend sends its confirmed demo fields, not its temporary scenario slider values. A newer browser version can import those fields; a newer backend version is returned to the frontend. This is the local demo's state synchronization contract, not a production accounting ledger.

Each completed model/tool step is recorded with its role and result; model usage is saved when supplied by the provider. The trace does not store private model reasoning. Completed turns can continue after restart; a run interrupted during an external call is marked interrupted rather than replayed automatically. A session is bound to its order and selected document. **New chat** starts a new session without deleting old activity.

A turn allows at most 18 model calls and four delegations; the Coordinator gets at most seven calls and each subagent invocation at most five. Limits include finalization. Subagents reserve one global call for the Coordinator to summarize their results; the final available call exposes only `finish`. A budget or connection failure preserves completed specialist output and records its failure category. All three specialists are invoked only when needed; normal dashboard rendering uses no model calls.

## Scope of this implementation

Implemented: replaceable provider transport, main/subagent tool loops, real MCP dispatch, persistent clarification, versioned citations, draft artifacts, deterministic cash scenarios, explicit confirmation and frontend synchronization.

Not part of this change: security experiment integration, autonomous background time/event scheduling, automatic bank-ledger reconciliation, a general multi-order accounting backend, real external email sending or lender submission. Existing frontend reminder demonstrations remain unchanged.

## Tests

```bash
# From tradex-rag/
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_agent_stack.py -m integration -q
```

The second command starts a temporary HTTP service and real stdio MCP bridge and exercises clarification, confirmation, cash analysis, decision drafting and citations. Only model responses and embeddings are test fixtures; no paid API calls are made. This proves the integration contract, not live model reliability. Real OpenRouter output quality and tool choices require a configured key and an explicit live test.

References: [OpenRouter tool calling](https://openrouter.ai/docs/guides/features/tool-calling), [OpenRouter model catalogue](https://openrouter.ai/api/v1/models), [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).

## Live execution progress

The browser starts a turn with `POST /api/assistant/runs`, receives its run/session IDs immediately, then polls `GET /api/agents/runs/{run_id}/progress` every 800 ms. The existing synchronous chat endpoint remains available. One POST starts one execution; polling and reconnection do not invoke a model. Pending run IDs are saved with the conversation so a page reload can resume observation.

The runtime records timestamped agent start/finish, model request start/completion and tool start/result/error events. The progress panel names the active role and operation, shows participating agents and the most recent steps, then collapses to an activity record when the response is ready. Status labels support English and Chinese. Progress updates replace only the progress panel, preserving unsent input. The panel presents execution metadata rather than hidden model reasoning, tool payloads or a simulated percentage.

Tasks execute on the backend independently of the selected page. A global **AI tasks** control shows running tasks and unread results; selecting a task opens its order/document conversation. Navigation and reload reconnect to the saved run instead of starting another execution. **New chat** archives visible turns while existing tasks continue; their completion does not replace the new conversation's session. Pending and unread tasks are retained when older visible history is trimmed. Backend process restarts still interrupt in-flight model calls.

## Human clarification

An agent can return up to three structured questions in its `finish` result. Each question supplies a short explanation and two to four options; the application adds a free-text note and a skip choice without preselecting an answer. The Coordinator merges specialist questions. Missing receipt amounts and dates also have workflow-derived question cards, so unsupported values remain empty.

Questions are saved with the originating run. `POST /api/agents/runs/{id}/answers` validates the question IDs and selections, stores the explicit answers/skips, and starts one continuation in the same conversation. Repeating the same submission returns the existing continuation ID. Answering an older turn after the conversation has advanced returns a conflict. The user can leave a note without selecting an option, skip individual questions, or skip all. Skipped fields remain unknown and are not automatically approved or written to the forecast. Payment proposal confirmation remains a separate step.

The frontend saves unfinished selections and notes across navigation/reload and observes the resumed run through the existing background task panel. Waiting for a human consumes no model calls. This implementation persists the business clarification and starts a new turn with its context; it does not checkpoint and resume an instruction inside a LangGraph node.

## Harness and tool boundaries

`agents/harness.py` connects `create_deep_agent` to the replaceable `ModelClient`. Each role uses the same provider transport and its configured model. Native Deep Agents delegation runs the business subagents, while tool calls reach the existing service through stdio MCP. Generic host filesystem and shell tools are excluded; the dedicated sandbox tool handles code execution.

Clarification remains a business workflow: the agent returns question cards, SQLite persists the answers, and a new turn continues with the same session context. It consumes no calls while waiting. Navigation and reload reconnect to the running backend task. This integration uses completed-turn persistence rather than resuming an interrupted model request inside a graph node.

## Public web evidence

The Coordinator and Decision roles receive `web_search` and `web_fetch` when `TRADEX_WEB_ENABLED=1`. Search uses the [OpenRouter web plugin](https://openrouter.ai/docs/guides/features/plugins/web-search) with the existing OpenRouter key and a separate, short public question. It does not attach conversation history or documents. Prompts require generalized policy queries without private customer details.

Each turn permits two searches with up to three results each. Search model usage is recorded separately from the 18-call business-agent budget; the provider also charges for web retrieval. `TRADEX_SEARCH_MODEL` selects the search model, independently of the main agent provider.

The reader accepts HTTPS pages on the issuing-authority and institution domains listed in `agents/extensions.py`, follows only approved-domain redirects, and reads HTML pages returned by a conversation's search. Search excerpts and fetched page text are distinct source records. Both retain URL, retrieval time and a saved passage; the answer cites numeric source IDs and the frontend opens the saved excerpt with a link to the public page. Agents read the page before asserting a policy condition or effective date. PDF policies continue through the document library.

## Isolated Python analysis

Cash-flow and Decision receive `sandbox_python` when `TRADEX_SANDBOX_ENABLED=1`. [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) creates a short-lived Docker container for each call. `/tmp/input.json` contains the current forecast and selected, already-authorized source excerpts. The script uses Python's standard library and prints its results, which are saved as a draft analysis artifact.

The container receives no host directories or provider credentials. It has one CPU, 512 MiB memory, a two-minute lifetime and a 20-second command timeout; code runs as UID 65534 with outbound networking denied. Each execution destroys its container. Financial updates still use explicit proposal confirmation, and `wf_cash` remains the authoritative calculation service. The initial tool processes extracted text and JSON; raw spreadsheet import and binary report export are separate future extensions.

### Local setup

From `tradex-rag/`, with Docker Desktop running:

```bash
.venv/bin/python -m pip install -e '.[test,sandbox]'
docker pull python:3.12-slim
docker pull opensandbox/execd:v1.1.0
docker pull opensandbox/egress:v1.1.7
.venv/bin/python scripts/setup_sandbox.py
.venv/bin/opensandbox-server --config var/sandbox.toml
```

Keep the sandbox service running and start `./start.sh` in another terminal. The setup script creates a local sandbox API key, writes authenticated loopback-only server settings under `var/`, and enables sandbox and web tools in `.env`. Both files remain excluded from Git. It preserves the existing model keys. Web search uses `OPENROUTER_API_KEY`, even when business agents use another provider.

To enable public search without a sandbox, add `TRADEX_WEB_ENABLED=1` to `.env` and restart the backend. To disable either feature, set its enable flag to `0`. `/api/agents/status` reports the selected harness and feature flags; sandbox availability also requires the local service and Docker to be running.
