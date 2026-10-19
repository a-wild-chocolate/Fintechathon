#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
project_dir="$PWD"
if [ -f tradex-rag/.env ]; then set -a; . tradex-rag/.env; set +a; fi
session="$(date +%Y%m%d-%H%M%S)-$$"
export TRADEX_DEMO_SESSION="$session"
export TRADEX_DATA_DIR="$project_dir/tradex-rag/var/empty-demos/$session"
export TRADEX_TENANT="empty-demo-$session"
export TRADEX_RAG_PORT=18770
export TRADEX_RAG_URL=http://127.0.0.1:18770
export PORT=5174
# Refuse occupied demo ports rather than attaching a new frontend to old data.
tradex-rag/.venv/bin/python - <<'CHECK'
import socket
for port in (5174, 18770):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', port))
CHECK
mkdir -p "$TRADEX_DATA_DIR"
tradex-rag/.venv/bin/python -m uvicorn tradex_rag.api:app --app-dir tradex-rag --host 127.0.0.1 --port "$TRADEX_RAG_PORT" &
backend_pid=$!
node scripts/serve.js &
frontend_pid=$!
trap 'kill "$frontend_pid" "$backend_pid" 2>/dev/null || true' EXIT
trap 'exit 0' INT TERM
printf 'Empty demo: http://127.0.0.1:5174/\nSession data: %s\n' "$TRADEX_DATA_DIR"
wait "$frontend_pid" "$backend_pid"
