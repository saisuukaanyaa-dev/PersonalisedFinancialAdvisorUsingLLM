#!/bin/sh
# Runs once per `docker compose up` in the n8n-setup container, before n8n itself starts.
set -e
echo "[pfa-setup] creating credentials from .env"
[ -n "$OPENAI_API_KEY" ] || echo "[pfa-setup] WARNING: OPENAI_API_KEY is empty - AI steps will fail until you add it to .env and run ./start.sh again"
node /pfa/bootstrap/make-credentials.js > /tmp/pfa-credentials.json
n8n import:credentials --input=/tmp/pfa-credentials.json
rm -f /tmp/pfa-credentials.json

# v3.4: the bank deposit planner now lives inside the advisor workflow. An install upgraded from v3.2/v3.3
# still has the old separate workflow; switch it off so its MCP path (/mcp/bank-deposits) is free.
echo "[pfa-setup] retiring the old separate deposit workflow (if present)"
n8n unpublish:workflow --id=pfaBankDepositsV1 >/dev/null 2>&1 || true

echo "[pfa-setup] importing workflows"
n8n import:workflow --input=/pfa/pfa_rag_ingestion.json
n8n import:workflow --input=/pfa/pfa_advisor_v3.4.json

echo "[pfa-setup] activating the advisor (app, chat, deposit planner, MCP servers)"
n8n publish:workflow --id=pfaAdvisorV32App
echo "[pfa-setup] done"
