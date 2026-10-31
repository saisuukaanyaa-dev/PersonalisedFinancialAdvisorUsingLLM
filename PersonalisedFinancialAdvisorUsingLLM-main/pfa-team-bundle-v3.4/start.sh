#!/usr/bin/env bash
# Starts the whole Personal Finance Advisor stack, including Phoenix observability.
# Safe to run again at any time.

set -euo pipefail

source "$(dirname "$0")/scripts/_common.sh"

# ------------------------------------------------------------
# 1. Check Docker
# ------------------------------------------------------------

docker info >/dev/null 2>&1 || {
  echo "Docker is not running. Start Docker Desktop and try again."
  exit 1
}

# ------------------------------------------------------------
# 2. Helper functions
# ------------------------------------------------------------

rand() {
  LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"
}

setenv() {
  # setenv KEY VALUE - portable in-place edit of .env
  local tmp
  tmp="$(mktemp)"

  awk -v k="$1" -v v="$2" '
    BEGIN { d=0 }
    $0 ~ "^"k"=" {
      print k"="v
      d=1
      next
    }
    { print }
    END {
      if (!d) print k"="v
    }
  ' .env > "$tmp" && mv "$tmp" .env
}

# ------------------------------------------------------------
# 3. Create .env if it does not exist
# ------------------------------------------------------------

if [[ ! -f .env ]]; then

  proj="${COMPOSE_PROJECT_NAME:-pfa}"

  if docker volume inspect "${proj}_pfa_n8n_data" >/dev/null 2>&1 ||
     docker volume inspect "${proj}_pfa_postgres_data" >/dev/null 2>&1; then

    echo "No .env found, but data from an earlier install exists (Docker volumes ${proj}_pfa_*)."
    echo "New random secrets would lock you out of that data."
    echo
    echo "Either:"
    echo "  - restore your previous .env into this folder, then run ./start.sh again, or"
    echo "  - wipe the old data and start clean:"
    echo "      docker compose -p ${proj} down -v"
    echo "    (or ./reset.sh once a .env exists)"
    exit 1
  fi

  cp .env.example .env

  setenv POSTGRES_PASSWORD "$(rand 32)"
  setenv N8N_ENCRYPTION_KEY "$(rand 48)"
  setenv MCP_BEARER_TOKEN "$(rand 40)"

  chmod 600 .env

  echo "Created .env with fresh random secrets."
fi

# ------------------------------------------------------------
# 4. Ask for OpenAI API key if not configured
# ------------------------------------------------------------

if [[ -z "$(envval OPENAI_API_KEY)" ]]; then

  if [[ -t 0 ]]; then
    read -r -s -p \
      "Paste your OpenAI API key (input hidden, Enter to skip): " key
    echo

    [[ -n "$key" ]] && setenv OPENAI_API_KEY "$key"
  fi

  [[ -z "$(envval OPENAI_API_KEY)" ]] && \
    echo "WARNING: no OpenAI key - forms open, but AI steps will fail. Add OPENAI_API_KEY to .env and run ./start.sh again."
fi

# ------------------------------------------------------------
# 5. Start core infrastructure + Phoenix observability
# ------------------------------------------------------------

echo
echo "=============================================================="
echo " Starting Personal Finance Advisor stack"
echo "=============================================================="
echo

echo "Starting PostgreSQL, Market API, Phoenix, Telemetry and the teammate service..."
echo "First run may download Docker images and take a few minutes."
if ! docker image inspect pfa-teammate-advisor:3.3 >/dev/null 2>&1; then
  echo "The teammate service image is built once now: about 10-15 minutes and 3.3 GB"
  echo "(Python, CPU-only PyTorch, the reranker and the two Chroma RAG stores)."
fi

$COMPOSE up -d --build \
  postgres \
  market-analyzer \
  phoenix \
  telemetry \
  teammate-advisor

# ------------------------------------------------------------
# 5b. Load the bank deposit rates (idempotent - replaces the table contents)
# ------------------------------------------------------------

echo -n "Loading bank deposit rates "
for i in $(seq 1 30); do
  $COMPOSE exec -T postgres pg_isready -U "$(envval POSTGRES_USER)" -d "$(envval POSTGRES_DB)" >/dev/null 2>&1 && break
  echo -n "."; sleep 2
done
$COMPOSE exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$(envval POSTGRES_USER)" -d "$(envval POSTGRES_DB)" < postgres/deposits.sql >/dev/null
echo "- $(psql_q "select count(*) from deposit_schemes") rows"
$COMPOSE exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$(envval POSTGRES_USER)" -d "$(envval POSTGRES_DB)" < postgres/v34.sql >/dev/null

# ------------------------------------------------------------
# 6. Show Phoenix / Telemetry status
# ------------------------------------------------------------

echo
echo "Checking observability services..."

$COMPOSE ps phoenix telemetry teammate-advisor 2>/dev/null || true

# ------------------------------------------------------------
# 7. Start n8n setup and n8n
# ------------------------------------------------------------

echo
echo "Starting n8n setup and n8n..."

# Always re-run setup and recreate n8n,
# so updated workflows/credentials in this folder take effect.
$COMPOSE up -d --force-recreate \
  n8n-setup \
  n8n

# ------------------------------------------------------------
# 8. Wait for n8n
# ------------------------------------------------------------

echo -n "Waiting for n8n "

for i in $(seq 1 90); do

  if [[ "$(
    $COMPOSE ps \
      --format '{{.Service}} {{.Health}}' 2>/dev/null |
      awk '$1=="n8n"{print $2}'
  )" == "healthy" ]]; then

    echo " ready"
    break
  fi

  echo -n "."
  sleep 2

  if [[ $i == 90 ]]; then
    echo
    echo "n8n did not become healthy."
    echo
    echo "See logs with:"
    echo "  $COMPOSE logs n8n-setup n8n"
    exit 1
  fi

done

# ------------------------------------------------------------
# 9. Test telemetry service
# ------------------------------------------------------------

echo
echo "Checking telemetry service..."

TEL_PORT="$(envval TELEMETRY_PORT)"; TEL_PORT="${TEL_PORT:-8001}"
if curl -fsS "http://localhost:${TEL_PORT}/health" >/dev/null 2>&1; then
  echo "Telemetry API: OK (every n8n run is sent to Phoenix, project pfa-n8n)"
else
  echo "WARNING: Telemetry API is not responding on port ${TEL_PORT}."
  echo "Check with:"
  echo "  $COMPOSE logs telemetry"
fi

TM_PORT="$(envval TEAMMATE_MCP_PORT)"; TM_PORT="${TM_PORT:-8090}"
echo -n "Teammate service "
for i in $(seq 1 60); do
  if curl -fsS "http://localhost:${TM_PORT}/health" >/dev/null 2>&1; then echo "OK"; break; fi
  echo -n "."; sleep 2
  if [[ $i == 60 ]]; then
    echo
    echo "WARNING: the teammate service is not answering yet. The advisor still works; only the"
    echo "bank-scheme and mutual-fund questions in the chats need it. Check: $COMPOSE logs teammate-advisor"
  fi
done

# ------------------------------------------------------------
# 10. Load knowledge base
# ------------------------------------------------------------

if [[ -n "$(envval OPENAI_API_KEY)" ]]; then

  echo
  echo "Loading the knowledge base (skips files already loaded)..."

  ./scripts/ingest-rag.sh || \
    echo "RAG ingestion stopped - run ./scripts/ingest-rag.sh to resume."
fi

# ------------------------------------------------------------
# 11. Display application URLs
# ------------------------------------------------------------

P="$(envval N8N_PORT)"
MARKET_PORT="$(envval MARKET_API_PORT)"
PHX_PORT="$(envval PHOENIX_PORT)"; PHX_PORT="${PHX_PORT:-6006}"

cat <<MSG

==============================================================
 Personal Finance Advisor is running
--------------------------------------------------------------

 Advisor app (start here)
   http://localhost:${P}/webhook/pfa
   Step form with Back / Edit, your plans, report + chat (plan changes with Yes / No)

 n8n
   Editor:
   http://localhost:${P}

   Hosted chat (same assistant as the report page):
   http://localhost:${P}/webhook/5b46aa0d-dea0-4fee-9081-a432d5d484ce/chat

 MCP
   Endpoint:
   http://localhost:${P}/mcp/pfa-finance-tools

   Bearer token:
   MCP_BEARER_TOKEN in .env

 Bank deposits (inside the advisor; ask in the chat)
   MCP endpoint (same bearer token):
   http://localhost:${P}/mcp/bank-deposits

 Market API
   http://localhost:${MARKET_PORT}/health

 Teammate service (PersonalisedFinancialAdvisorUsingLLM, MCP)
   http://localhost:${TM_PORT}/mcp   (same bearer token)
   Health: http://localhost:${TM_PORT}/health

 Phoenix
   Dashboard:  http://localhost:${PHX_PORT}
   Projects:   pfa-n8n (every workflow run), pfa-teammate-advisor (the teammate service)

 Telemetry API
   Health:
   http://localhost:${TEL_PORT}/health

--------------------------------------------------------------
 Test plan: TESTING.md
 Health:    ./healthcheck.sh
 Stop:      ./stop.sh
==============================================================

MSG