#!/usr/bin/env bash
# Status of every service, plus counts of accounts, plans and knowledge-base chunks.
set -euo pipefail
source "$(dirname "$0")/scripts/_common.sh"
$COMPOSE ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}'
echo
curl -fsS "http://localhost:$(envval APP_PORT)/healthz" && echo || echo "App health endpoint not reachable."
echo "Accounts: $(psql_q 'select count(*) from accounts' 2>/dev/null || echo '?')   Plans: $(psql_q 'select count(*) from advice_sessions' 2>/dev/null || echo '?')"
