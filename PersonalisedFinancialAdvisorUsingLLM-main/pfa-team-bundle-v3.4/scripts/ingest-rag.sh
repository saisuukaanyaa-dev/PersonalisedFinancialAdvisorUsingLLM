#!/usr/bin/env bash
# Loads knowledge-base/*.md into pgvector - batched, parallel, resumable (see scripts/rag-ingest.mjs).
#   ./scripts/ingest-rag.sh                              load new or changed files; resumes after a stop
#   ./scripts/ingest-rag.sh --force                      wipe and reload everything
#   ./scripts/ingest-rag.sh --concurrency 8 --batch 128  faster (use 2 / 48 if you hit rate limits)
#   ./scripts/ingest-rag.sh --dry-run                    show what would be loaded, call nothing
set -euo pipefail
source "$(dirname "$0")/_common.sh"
OPENAI_API_KEY="$(envval OPENAI_API_KEY)"; export OPENAI_API_KEY
OPENAI_BASE_URL="$(envval OPENAI_BASE_URL)"; export OPENAI_BASE_URL
[[ -n "$OPENAI_API_KEY" || " $* " == *" --dry-run "* ]] || { echo "Add OPENAI_API_KEY to .env first, then run ./start.sh."; exit 1; }
# One-off container from the n8n image: same network, DB settings and knowledge-base mount as n8n.
exec $COMPOSE run --rm --no-deps -T -e OPENAI_API_KEY -e OPENAI_BASE_URL \
  -v "$HOST_PWD/scripts:/pfa-scripts:ro" --entrypoint node n8n /pfa-scripts/rag-ingest.mjs "$@"
