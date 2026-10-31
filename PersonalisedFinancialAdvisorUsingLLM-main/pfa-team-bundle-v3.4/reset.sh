#!/usr/bin/env bash
# Deletes ALL local data (profiles, reports, chat history, embeddings, n8n settings) and stops the stack.
set -euo pipefail
source "$(dirname "$0")/scripts/_common.sh"
read -r -p "This permanently deletes all local PFA data. Type 'reset' to continue: " ans
[[ "$ans" == "reset" ]] || { echo "Cancelled."; exit 0; }
$COMPOSE down -v
echo "Done. Run ./start.sh for a clean install (your .env is kept)."
