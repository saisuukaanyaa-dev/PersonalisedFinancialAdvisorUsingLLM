#!/usr/bin/env bash
# Stops the stack. Your data is kept.
set -euo pipefail
source "$(dirname "$0")/scripts/_common.sh"
$COMPOSE stop
