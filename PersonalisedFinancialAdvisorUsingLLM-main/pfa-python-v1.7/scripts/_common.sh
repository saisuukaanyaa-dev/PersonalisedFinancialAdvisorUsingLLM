# Shared helpers for the bundle scripts (sourced, not run).
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"
else echo "Docker Compose not found. Install Docker Desktop (or Docker Engine + compose plugin)." >&2; exit 1; fi
envval() { { grep -E "^$1=" .env 2>/dev/null || true; } | tail -1 | cut -d= -f2-; }  # empty if unset (never fails under set -e)
psql_q() { $COMPOSE exec -T postgres psql -U "$(envval POSTGRES_USER)" -d "$(envval POSTGRES_DB)" -tAc "$1"; }
