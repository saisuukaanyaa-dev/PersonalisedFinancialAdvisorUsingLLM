#!/usr/bin/env bash
# Starts the Personal Finance Advisor (Python edition). Safe to run again at any time.
set -euo pipefail
source "$(dirname "$0")/scripts/_common.sh"

docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again."; exit 1; }

rand() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
setenv() {  # setenv KEY VALUE - portable in-place edit of .env
  local tmp; tmp="$(mktemp)"
  awk -v k="$1" -v v="$2" 'BEGIN{d=0} $0 ~ "^"k"=" {print k"="v; d=1; next} {print} END{if(!d) print k"="v}' .env > "$tmp" && mv "$tmp" .env
}

if [[ ! -f .env ]]; then
  proj="${COMPOSE_PROJECT_NAME:-pfapy}"
  if docker volume inspect "${proj}_pg_data" >/dev/null 2>&1; then
    echo "No .env found, but data from an earlier install exists (Docker volume ${proj}_pg_data)."
    echo "Restore your previous .env into this folder, or wipe the old data:  $COMPOSE -p ${proj} down -v"
    exit 1
  fi
  cp .env.example .env
  setenv POSTGRES_PASSWORD "$(rand 32)"
  setenv SESSION_SECRET "$(rand 48)"
  chmod 600 .env
  echo "Created .env with fresh random secrets."
fi

if [[ -z "$(envval OPENAI_API_KEY)" && -t 0 ]]; then
  read -r -s -p "Paste your OpenAI API key (input hidden, Enter to skip): " key; echo
  [[ -n "$key" ]] && setenv OPENAI_API_KEY "$key"
fi
[[ -z "$(envval OPENAI_API_KEY)" ]] && echo "Note: no OpenAI key - plans and charts work; AI explanations and chat are off until you add OPENAI_API_KEY to .env."

echo "Starting containers (first run builds the app image - a few minutes)..."
$COMPOSE up -d --build

echo -n "Waiting for the app "
for i in $(seq 1 90); do
  if [[ "$($COMPOSE ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="app"{print $2}')" == "healthy" ]]; then echo " ready"; break; fi
  echo -n "."; sleep 2
  [[ $i == 90 ]] && { echo; echo "The app did not become healthy. See: $COMPOSE logs app"; exit 1; }
done

# Live data: the app updates the knowledge base from SerpAPI on start (at most once a day). Show its progress.
if [[ -n "$(envval SERPAPI_API_KEY)" ]]; then
  last=""
  for i in $(seq 1 90); do
    st="$(curl -fsS "http://localhost:$(envval APP_PORT)/api/kb/status" 2>/dev/null || true)"
    state="$(printf '%s' "$st" | sed -n 's/.*"state":"\([a-z]*\)".*/\1/p')"
    msg="$(printf '%s' "$st" | sed -n 's/.*"message":"\([^"]*\)".*/\1/p')"
    [[ -n "$msg" && "$msg" != "$last" ]] && { echo "  $msg"; last="$msg"; }
    [[ "$state" == "updating" || "$state" == "idle" ]] || break
    sleep 2
  done
fi

if [[ -n "$(envval OPENAI_API_KEY)" ]]; then
  echo "Loading the knowledge base (skips files already loaded)..."
  ./scripts/ingest-rag.sh || echo "Knowledge-base loading stopped - run ./scripts/ingest-rag.sh to resume."
fi

P="$(envval APP_PORT)"; PH="$(envval PHOENIX_PORT)"
G="$( [[ -n "$(envval GOOGLE_CLIENT_ID)" ]] && echo 'on' || echo 'off (email + password only - see README)')"
cat <<MSG

==============================================================
 Personal Finance Advisor (Python edition) is running
--------------------------------------------------------------
 Open           http://localhost:${P:-8080}
 Traces         http://localhost:${PH:-6006}   (Phoenix: every plan and chat question, step by step)
 Google sign-in ${G}
--------------------------------------------------------------
 Test plan: TESTING.md    Health: ./healthcheck.sh    Stop: ./stop.sh
==============================================================
MSG
