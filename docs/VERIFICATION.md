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
