#!/usr/bin/env bash
# Starts the Optimal Bank Deposit Finder MCP server (streamable-http transport).
#
# Usage:
#   ./start.sh            # serve on http://127.0.0.1:8090/mcp
#   ./start.sh 9000       # serve on a custom port
#   MCP_PORT=9000 ./start.sh
#   ./start.sh dev        # open the MCP Inspector UI instead (mcp dev)
#   ./start.sh docker     # build and run the server in docker (compose)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Folder holding the .py files (change here if it is ever renamed)
SOURCE_DIR="source"

if [ "${1:-}" = "docker" ]; then
    if [ ! -f ".env" ]; then
        echo "Error: .env not found. Copy .env.example to .env and fill in the keys." >&2
        exit 1
    fi
    if [ ! -f "memory.db" ]; then
        echo "Error: memory.db not found. Run 'uv run python ${SOURCE_DIR}/DatabaseCreator.py' first." >&2
        exit 1
    fi
    echo "Starting MCP server on http://127.0.0.1:${MCP_PORT:-8090}/mcp and n8n on http://127.0.0.1:${N8N_PORT:-5678}"
    exec docker compose up --build
fi

SERVER_FILE="${SOURCE_DIR}/MCPServerForOptimalBankDepositFinderAgent.py"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv not found. Install it from https://docs.astral.sh/uv/" >&2
    exit 1
fi

export PYTHONIOENCODING="utf-8"

if [ "${1:-}" = "dev" ]; then
    exec uv run mcp dev "$SERVER_FILE"
fi

if [ -n "${1:-}" ]; then
    export MCP_PORT="$1"
fi
export MCP_PORT="${MCP_PORT:-8090}"

echo "Starting MCP server on http://127.0.0.1:${MCP_PORT}/mcp"
exec uv run python "$SERVER_FILE"
