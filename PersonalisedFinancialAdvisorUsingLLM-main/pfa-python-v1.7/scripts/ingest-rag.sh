#!/usr/bin/env bash
# Load the knowledge base into pgvector. Resumable. Options: --force --dry-run --batch N --concurrency N
set -euo pipefail
source "$(dirname "$0")/_common.sh"
$COMPOSE exec -T app python -m pfa.ingest "$@"
