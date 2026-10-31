# Shared helpers for the bundle scripts (sourced, not run).
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Git Bash on Windows rewrites arguments that look like Unix paths (/pfa-scripts/x.mjs ->
# C:/Program Files/Git/pfa-scripts/x.mjs) before docker sees them. Container paths must stay as written.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
# This folder as Docker on the host expects it for -v mounts (C:/Users/... on Git Bash, $PWD elsewhere).
HOST_PWD="$(pwd -W 2>/dev/null || pwd)"
if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"
else echo "Docker Compose not found. Install Docker Desktop (or Docker Engine + compose plugin)." >&2; exit 1; fi
# A key missing from .env reads as empty (grep would otherwise fail the caller under set -e / pipefail).
envval() { { grep -E "^$1=" .env 2>/dev/null || true; } | tail -1 | cut -d= -f2-; }
psql_q() { $COMPOSE exec -T postgres psql -U "$(envval POSTGRES_USER)" -d "$(envval POSTGRES_DB)" -tAc "$1"; }
# Rows in the RAG table; 0 if ingestion has never run (the table is created by the first ingestion).
kb_count() {
  if [[ "$(psql_q "select to_regclass('public.finance_kb_embeddings') is not null")" == "t" ]]; then
    psql_q "select count(*) from finance_kb_embeddings"
  else echo 0; fi
}
