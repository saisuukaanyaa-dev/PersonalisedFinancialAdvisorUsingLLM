#!/usr/bin/env bash
# AI cost per user: plans, chat questions, average cost per plan and per question.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
$COMPOSE exec -T app python -m pfa.usage_report
