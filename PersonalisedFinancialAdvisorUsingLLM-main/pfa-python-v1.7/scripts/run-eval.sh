#!/usr/bin/env bash
# Chat evaluation (local vs web vs router) -> docs/EVALUATION.md and docs/eval_answers.json
# Uses your OpenAI key (~₹10 for all modes) and ~30 SerpAPI searches. Options: --modes hybrid  --limit 10
set -euo pipefail
source "$(dirname "$0")/_common.sh"
$COMPOSE exec -T app python -m pfa.eval.run "$@" > docs/EVALUATION.md
$COMPOSE exec -T app cat /tmp/eval_answers.json > docs/eval_answers.json
echo "Written docs/EVALUATION.md"
head -12 docs/EVALUATION.md
