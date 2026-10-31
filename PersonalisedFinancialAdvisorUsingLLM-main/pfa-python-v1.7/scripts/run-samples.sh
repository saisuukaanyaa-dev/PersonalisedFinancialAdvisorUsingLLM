#!/usr/bin/env bash
# Sample run: 10 made-up personas x Low / Medium / High risk -> one PDF report each + a summary PDF.
#   ./scripts/run-samples.sh            all 30 plans  (about Rs 15 with gpt-5-mini)
#   ./scripts/run-samples.sh 2,7        only personas 2 and 7
# Output: test-output/samples-<date-time>/  (sampleNN-<risk>.pdf, summary.pdf, summary.json)
# Needs the stack running (./start.sh) and Google Chrome (prints the PDFs).
set -euo pipefail
source "$(dirname "$0")/_common.sh"

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
command -v "$CHROME" >/dev/null 2>&1 || [[ -x "$CHROME" ]] || CHROME="$(command -v google-chrome || command -v chromium || true)"
[[ -n "$CHROME" ]] || { echo "Google Chrome not found - set CHROME=/path/to/chrome"; exit 1; }

OUT="test-output/samples-$(date +%Y%m%d-%H%M)"
mkdir -p "$OUT"
APP="$($COMPOSE ps -q app)"
[[ -n "$APP" ]] || { echo "The app is not running - run ./start.sh first."; exit 1; }

echo "Building plans (10 personas x Low / Medium / High) - about 10-20 seconds each..."
docker exec "$APP" rm -rf /tmp/pfa-samples
set +e
docker exec "$APP" python -m pfa.eval.samples --out /tmp/pfa-samples ${1:+--only "$1"}
status=$?
set -e
docker cp "$APP:/tmp/pfa-samples/." "$OUT/"

echo "Printing PDFs..."
for f in "$OUT"/*.html; do
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="${f%.html}.pdf" "file://$PWD/$f" >/dev/null 2>&1
done
rm -f "$OUT"/*.html
echo "Done: $OUT  ($(ls "$OUT"/*.pdf | wc -l | tr -d ' ') PDFs)"
exit $status
