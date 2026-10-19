# Knowledge API contract

The browser calls same-origin `/api` endpoints. `scripts/serve.js` streams requests to the local RAG backend, including multipart uploads. API credentials stay in the backend process.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Document counts, embedding model and index state |
| `GET /api/documents` | Accessible company documents and public policies |
| `POST /api/uploads` | Multipart `file`, optional `title` and `order_id`; returns HTTP 202 with document and job IDs |
| `GET /api/documents/{id}` | Current text, source locations and version history |
| `GET /api/documents/{id}/versions/{version}` | Parsed text for a specific version |
| `GET /api/documents/{id}/versions/{version}/original` | Download the original bytes for that version |
| `GET /api/assistant/status` | `evidence`, legacy `model`, or `multi_agent` mode |
| `POST /api/assistant/chat` | Run the configured agent workflow or return retrieval excerpts |

## Chat request

```json
{
  "question": "What is the payment amount and date?",
  "language": "en",
  "document_id": null,
  "order_id": "TF-26104",
  "history": []
}
```

A selected `document_id` narrows retrieval to that document. An `order_id` includes that order, shared company files and public policies, while excluding other orders. The backend supplies the tenant context. Prior turns contain `question` and `answer` strings, with at most four turns.

## Chat response

```json
{
  "mode": "evidence",
  "model": null,
  "paragraphs": [{"text": "Source passage", "sources": [1]}],
  "sources": [{
    "id": 1,
    "document_id": "document-uuid",
    "version": 1,
    "title": "Buyer email",
    "excerpt": "Source passage",
    "context": "Surrounding source text",
    "locator": "paragraph 2",
    "source_url": null,
    "original_url": "/api/documents/document-uuid/versions/1/original",
    "review_due": false
  }],
  "follow_up": "",
  "semantic_available": true
}
```

Source IDs belong to one response. URLs, versions and locations come from the retrieval service, not model-generated links. The model must reference existing source IDs; paragraphs and source text are rendered as escaped text. An empty search returns no factual answer.

The document list polls every four seconds to show background processing. It refreshes library rows and the search-scope selector without replacing an unsent chat message. Upload errors are visible; they do not create successful financial updates.

## Multi-agent endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/agents/status` | Role models, provider and configuration status, without credentials |
| `GET /api/agents/workspace` | Latest accepted demo financial snapshot |
| `GET /api/agents/runs/{id}` | Persisted run status, source references and public tool trace |
| `POST /api/agents/proposals/{id}/confirm` | User confirmation of a complete receipt proposal; returns before/after cash results and workspace version |
| `POST /api/agent-tools/{name}` | MCP bridge dispatch; receives host-owned run ID, role and arguments |

Chat accepts optional `session_id` and `workspace` fields. Workspace fields are `version`, `opening`, `supplierDay`, `receiptDay` and `amountUSD`; dates use the existing demo's day offsets from 17 October 2026. The frontend sends confirmed fields rather than temporary scenario controls.

Multi-agent responses preserve `paragraphs`, `sources` and `follow_up` and add `mode: multi_agent`, `task_status`, `session_id`, `run_id`, `proposal`, `trace` and `workspace`. A result can need information, need approval, complete, or fail. Model/tool failures remain visible as a failed run rather than a successful financial update.

Session IDs are bound to the selected order and document. Agent history is loaded from SQLite; the browser's `history` field remains for legacy retrieval chat. The confirmation endpoint is not exposed as a model tool. A stale source or financial version returns HTTP 409. Existing evidence uploads and citations continue to use the same endpoints.

### Live agent progress

- `POST /api/assistant/runs`: same body as `/api/assistant/chat`; returns HTTP 202 with `run_id`, `session_id`, and `status: running` before model execution completes. Requires the agent service to be enabled.
- `GET /api/agents/runs/{run_id}/progress`: returns current status, creation time, timestamped activity metadata and the final `result` once available. Polling does not initiate another model call. Activity entries contain only event, agent, tool, status and timestamp fields; the final result follows the normal assistant response contract.

The frontend polls every 800 ms and saves the run ID to reconnect after reload. Terminal statuses include `completed`, `needs_information`, `needs_approval`, `failed` and `interrupted`.

## Structured human clarification

A `needs_information` response can contain `questions`: up to three objects with `id`, `question`, `context`, and two to four `options` strings. The frontend adds comments and skipping. Submit every displayed question once to `POST /api/agents/runs/{run_id}/answers`:

```json
{
  "language": "en",
  "answers": [
    {"question_id": "question-uuid", "action": "answer", "option_index": 1, "comment": "The supplier agreed to ten more days."}
  ]
}
```

`option_index` is zero-based and may be null when the user provides a comment. A skipped answer uses `action: "skip"` and a null index; comments remain optional. HTTP 202 returns `run_id`, `session_id`, `status`, and normalized `answers`. Observe that run through the progress endpoint. Identical retries return the same continuation rather than dispatching another model call. The original run's result gains `human_response`. This endpoint records clarification; it never confirms a receipt proposal or modifies accepted cash fields.

## Harness extensions

`GET /api/agents/status` includes `harness: "deepagents"`, `web_search_enabled` and `sandbox_enabled`. Feature flags describe configuration; Docker and the sandbox service must also be running for execution.

The MCP business endpoint adds `web_search(query)`, `web_fetch(url)` and `sandbox_python(code, source_ids)`. The host injects run and role context. Web evidence uses the existing numeric citation IDs with `kind: "web"`, `source_url`, `retrieved_at`, `locator` and `excerpt`. The frontend opens the saved passage and public URL without requesting a library document ID. Sandbox results contain stdout, stderr, exit code and a saved artifact ID.
