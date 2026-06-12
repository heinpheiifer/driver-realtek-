#!/usr/bin/env bash
# Find your original chart HTML anywhere under the old app folder.
set -euo pipefail

OLD_APP="${1:-/home/heinz/opentrade-app}"

echo "=== Searching for chart HTML in $OLD_APP ==="
echo ""

if [[ ! -d "$OLD_APP" ]]; then
  echo "Folder not found: $OLD_APP"
  exit 1
fi

echo "--- All HTML files (excluding .venv, backups, engine) ---"
find "$OLD_APP" \
  -path "$OLD_APP/.venv" -prune -o \
  -path "$OLD_APP/.opentrader_ui_backup" -prune -o \
  -path "$OLD_APP/opentrader/engine_static" -prune -o \
  -name '*.html' -print 2>/dev/null | head -40

echo ""
echo "--- Likely OLD chart (has heikin/bookmap, not git engine) ---"
while IFS= read -r f; do
  if grep -qiE 'heikin|drawing|lightweight-charts' "$f" 2>/dev/null && \
     ! grep -q 'runBacktestBtn' "$f" 2>/dev/null; then
    echo "  ★ $f"
  fi
done < <(find "$OLD_APP" \
  -path "$OLD_APP/.venv" -prune -o \
  -path "$OLD_APP/.opentrader_ui_backup" -prune -o \
  -name '*.html' -print 2>/dev/null)

echo ""
echo "--- Git NEW app (wrong UI) ---"
grep -rl 'runBacktestBtn' "$OLD_APP" --include='*.html' 2>/dev/null | head -5 || echo "  (none)"

echo ""
echo "If you found your chart path, add to $OLD_APP/.env :"
echo "  OPENTRADER_UI_INDEX=/full/path/to/your/chart.html"
