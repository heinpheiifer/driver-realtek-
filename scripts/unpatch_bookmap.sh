#!/usr/bin/env bash
# Remove ALL Bookmap layout patches from ~/OpenTrader (restore original UI).
#
# Usage:
#   bash scripts/unpatch_bookmap.sh
#   bash scripts/unpatch_bookmap.sh /home/heinz/OpenTrader
#   PURGE=1 bash scripts/unpatch_bookmap.sh   # also delete chart_patch folders
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PURGE="${PURGE:-1}"

_needs_strip() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  grep -qE 'bookmap_below_chart|bookmap_layout|ot-bookmap-below|chart_patch/' "$file" 2>/dev/null
}

_strip_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if ! _needs_strip "$file"; then
    return 0
  fi
  sed -i \
    -e 's|[[:space:]]*<link rel="stylesheet" href="[^"]*chart_patch/bookmap[^"]*"[^>]*/>[[:space:]]*||g' \
    -e 's|[[:space:]]*<script src="[^"]*chart_patch/bookmap[^"]*"[^>]*></script>[[:space:]]*||g' \
    -e 's|[[:space:]]*<script src="[^"]*chart_patch/bookmap[^"]*"[^>]*/>[[:space:]]*||g' \
    -e 's|<style id="ot-bookmap-below-inline">[^<]*</style>||g' \
    "$file"
  echo "  cleaned: $file"
}

_purge_dirs() {
  local dir
  for dir in \
    "$CHART_ROOT/frontend/dist/chart_patch" \
    "$CHART_ROOT/static/chart_patch" \
    "$CHART_ROOT/staticfiles/chart_patch"; do
    if [[ -d "$dir" ]]; then
      rm -rf "$dir"
      echo "  deleted: $dir"
    fi
  done
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
    -path '*/site-packages/*' -prune -o \
    -name 'index.html' -print 2>/dev/null
)

if [[ "$PURGE" == "1" ]]; then
  echo "==> Purging chart_patch asset folders (stops Firefox loading bad JS)"
  _purge_dirs
fi

echo ""
echo "Verify clean (should print nothing):"
grep -nE 'bookmap_below|bookmap_layout|ot-bookmap|chart_patch/' \
  "$CHART_ROOT/frontend/dist/index.html" 2>/dev/null || echo "  frontend/dist/index.html — OK"
echo ""
echo "Restart: bash scripts/run_my_old_app.sh"
echo "Firefox: clear site cache, then open http://127.0.0.1:8010"
