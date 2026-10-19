#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
exec .venv/bin/python -m uvicorn tradex_rag.api:app --host 127.0.0.1 --port "${TRADEX_RAG_PORT:-8765}"
