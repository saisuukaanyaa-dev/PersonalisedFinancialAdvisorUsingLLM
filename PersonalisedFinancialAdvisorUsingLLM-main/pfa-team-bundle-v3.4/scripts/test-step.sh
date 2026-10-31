#!/usr/bin/env bash
# Sends one step of the advisor app to n8n, so you can watch that part of the workflow on the canvas.
#
#   ./scripts/test-step.sh <step> [--live] [ID]
#
#   step     app | lookup | submit | status | report | chat | chat-change | confirm | confirm-no
#   --test   (default) n8n's test URL /webhook-test/... - first click "Execute workflow" in the editor
#            and pick the matching trigger ("from Submit API", ...), then run this within 2 minutes
#   --live   the real URL /webhook/... - shows up afterwards in the Executions tab
#   ID       report id for status/report/chat/chat-change, or the pending-change id
#            (confirm.id in the chat-change reply) for confirm
#
# Request bodies are in testing/payloads/*.json - edit them to try other answers.
set -euo pipefail
source "$(dirname "$0")/_common.sh"

STEP="${1:-}"; shift || true
MODE="webhook-test"; ID=""
for a in "$@"; do
  case "$a" in
    --live) MODE="webhook" ;;
    --test) MODE="webhook-test" ;;
    *) ID="$a" ;;
  esac
done
PORT="$(envval N8N_PORT)"; BASE="http://localhost:${PORT:-5678}/$MODE/pfa"
P="testing/payloads"

need_id() { [[ -n "$ID" ]] || { echo "This step needs an id: ./scripts/test-step.sh $STEP ${MODE/webhook-test/--test} <id>" >&2; exit 1; }; }
post() { # post PATH FILE [placeholder]
  local body; body="$(cat "$2")"
  [[ -n "${3:-}" ]] && body="${body//$3/$ID}"
  echo "POST $BASE/$1"
  curl -sS -X POST "$BASE/$1" -H 'Content-Type: application/json' --data "$body"; echo
}

case "$STEP" in
  app)     echo "GET $BASE"; curl -sS -o /dev/null -w 'HTTP %{http_code}, %{size_download} bytes of HTML\n' "$BASE" ;;
  lookup)  post lookup "$P/lookup.json" ;;
  submit)  post submit "$P/submit.json" ;;
  status)  need_id; echo "GET $BASE/status?id=$ID"; curl -sS "$BASE/status?id=$ID"; echo ;;
  report)  need_id; echo "GET $BASE/report?id=$ID"; curl -sS -o /dev/null -w 'HTTP %{http_code}, %{size_download} bytes of HTML\n' "$BASE/report?id=$ID" ;;
  chat)    need_id; post chat "$P/chat.json" REPORT_ID ;;
  chat-change) need_id; post chat "$P/chat-change.json" REPORT_ID ;;
  confirm) need_id; post confirm "$P/confirm.json" PENDING_CHANGE_ID ;;      # Yes: applies it, rebuilds the plan
  confirm-no) need_id; post confirm "$P/confirm-no.json" PENDING_CHANGE_ID ;; # No: discards it
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
