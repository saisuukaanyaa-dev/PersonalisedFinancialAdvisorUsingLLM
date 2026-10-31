#!/usr/bin/env bash
# Deletes ALL local data (accounts, profiles, reports, knowledge base) and containers.
set -euo pipefail
source "$(dirname "$0")/scripts/_common.sh"
read -r -p "This deletes all local accounts, plans and the loaded knowledge base. Type DELETE to continue: " ok
[[ "$ok" == "DELETE" ]] || { echo "Cancelled."; exit 1; }
$COMPOSE down -v --remove-orphans
echo "Done. Run ./start.sh for a clean install."
