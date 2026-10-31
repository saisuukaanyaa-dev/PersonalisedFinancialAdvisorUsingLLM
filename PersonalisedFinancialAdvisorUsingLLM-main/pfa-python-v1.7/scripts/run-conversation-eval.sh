#!/usr/bin/env bash
# Conversation evaluation (tone, confirm-before-change, watchlist, no repeated refusals) -> docs/CONVERSATION_EVAL.md
# Uses your OpenAI key: 8 conversations + a judge call per reply, about ₹3-5.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
$COMPOSE exec -T app python -m pfa.eval.run --conversations > docs/CONVERSATION_EVAL.md
echo "Written docs/CONVERSATION_EVAL.md"; head -6 docs/CONVERSATION_EVAL.md
