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
| `GET /api/assistant/status` | `evidence` or `model` mode |
| `POST /api/assistant/chat` | Retrieve evidence and return excerpts or a Qwen answer |

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
