#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec .venv/bin/python -m tradex_rag.mcp_server
