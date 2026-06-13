#!/usr/bin/env bash
# Remove Bookmap layout patches from ~/OpenTrader (restore original UI).
#
# Usage:
#   bash scripts/unpatch_bookmap.sh
#   bash scripts/unpatch_bookmap.sh /home/heinz/OpenTrader
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"

_strip_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if ! grep -q "bookmap_below_chart.css" "$file" 2>/dev/null; then
    return 0
  fi
  sed -i \
    -e 's|[[:space:]]*<link rel="stylesheet" href="[^"]*chart_patch/bookmap_below_chart\.css"[^>]*/>[[:space:]]*||g' \
    -e 's|[[:space:]]*<script src="[^"]*chart_patch/bookmap_layout\.js"[^>]*></script>[[:space:]]*||g' \
    -e 's|[[:space:]]*<script src="[^"]*chart_patch/bookmap_layout\.js"[^>]*/>[[:space:]]*||g' \
    -e 's|<style id="ot-bookmap-below-inline">[^<]*</style>||g' \
    "$file"
  echo "  cleaned: $file"
}

echo "==> Removing Bookmap layout patches from $CHART_ROOT"

for html in \
  "$CHART_ROOT/frontend/dist/index.html" \
  "$CHART_ROOT/frontend/index.html" \
  "$CHART_ROOT/staticfiles/index.html" \
  "$CHART_ROOT/static/index.html" \
  "$CHART_ROOT/index.html"; do
  _strip_file "$html"
done

while IFS= read -r html; do
  _strip_file "$html"
done < <(
  find "$CHART_ROOT" \
    -path '*/.venv/*' -prune -o \
    -path '*/node_modules/*' -prune -o \
    -name 'index.html' -print 2>/dev/null
)

echo ""
echo "Done. Restart: bash scripts/run_my_old_app.sh"
echo "Hard-refresh Firefox: Ctrl+Shift+R on http://127.0.0.1:8010"
