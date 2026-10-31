#!/usr/bin/env bash
# Quick status of every part of the stack.
set -uo pipefail
source "$(dirname "$0")/scripts/_common.sh"
ok() { printf '  %-22s %s\n' "$1" "$2"; }
echo "Containers:"; $COMPOSE ps --format '  {{.Service}}\t{{.State}}\t{{.Health}}'
echo; echo "Checks:"
curl -fsS "http://localhost:$(envval MARKET_API_PORT)/health" >/dev/null 2>&1 && ok "market-analyzer" "OK" || ok "market-analyzer" "NOT RESPONDING"
curl -fsS "http://localhost:$(envval N8N_PORT)/healthz" >/dev/null 2>&1 && ok "n8n" "OK" || ok "n8n" "NOT RESPONDING"
code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$(envval N8N_PORT)/webhook/pfa")
[[ "$code" == "200" ]] && ok "advisor app" "OK  http://localhost:$(envval N8N_PORT)/webhook/pfa" || ok "advisor app" "HTTP $code (workflow not active?)"
ok "users saved" "$(psql_q 'select count(*) from users' 2>/dev/null || echo '?')"
ok "reports saved" "$(psql_q 'select count(*) from advice_sessions' 2>/dev/null || echo '?')"
kb=$(kb_count 2>/dev/null || echo '?')
ok "RAG chunks" "$kb$([[ "$kb" == "0" ]] && echo '  -> run ./scripts/ingest-rag.sh')"
[[ -n "$(envval OPENAI_API_KEY)" ]] && ok "OpenAI key" "set" || ok "OpenAI key" "MISSING in .env"
port() { local v; v="$(envval "$1")"; echo "${v:-$2}"; }
curl -fsS "http://localhost:$(port PHOENIX_PORT 6006)/healthz" >/dev/null 2>&1 && ok "phoenix" "OK  http://localhost:$(port PHOENIX_PORT 6006)" || ok "phoenix" "NOT RESPONDING"
tel=$(curl -fsS "http://localhost:$(port TELEMETRY_PORT 8001)/health" 2>/dev/null)
if [[ -n "$tel" ]]; then
  ok "telemetry" "$(echo "$tel" | python3 -c 'import json,sys; d=json.load(sys.stdin); e=d.get("last_error"); print("OK  %s runs / %s spans sent to Phoenix%s" % (d["executions_exported"], d["spans_exported"], "  last error: %s" % e if e else ""))' 2>/dev/null || echo OK)"
else ok "telemetry" "NOT RESPONDING"; fi
tm=$(curl -fsS "http://localhost:$(port TEAMMATE_MCP_PORT 8090)/health" 2>/dev/null)
[[ -n "$tm" ]] && ok "teammate service" "OK  $tm" || ok "teammate service" "NOT RESPONDING (chats still work, without bank-scheme / fund answers)"
