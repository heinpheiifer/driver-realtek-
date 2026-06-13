#!/usr/bin/env bash
# Patch ~/OpenTrader UI: Bookmap Order Flow below chart (not on the right).
#
# Usage:
#   bash scripts/patch_bookmap_below_chart.sh
#   bash scripts/patch_bookmap_below_chart.sh /home/heinz/OpenTrader
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PATCH_SRC="$ENGINE_ROOT/opentrader/chart_patches"
PATCH_DEST="$CHART_ROOT/static/chart_patch"

if [[ ! -d "$CHART_ROOT" ]]; then
  echo "ERROR: $CHART_ROOT not found"
  exit 1
fi

echo "==> Patching Bookmap layout: $CHART_ROOT"
mkdir -p "$PATCH_DEST"
cp "$PATCH_SRC/bookmap_below_chart.css" "$PATCH_DEST/"
cp "$PATCH_SRC/bookmap_layout.js" "$PATCH_DEST/"

_inject_html() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if grep -q "chart_patch/bookmap_below_chart.css" "$file" 2>/dev/null; then
    echo "  already patched: $file"
    return 0
  fi
  # Django / Vite index.html
  if grep -qi '</head>' "$file"; then
    sed -i 's|</head>|  <link rel="stylesheet" href="/static/chart_patch/bookmap_below_chart.css" />\n  <script src="/static/chart_patch/bookmap_layout.js" defer></script>\n</head>|' "$file"
    echo "  patched: $file"
  fi
}

_inject_template() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if grep -q "chart_patch/bookmap_below_chart.css" "$file" 2>/dev/null; then
    return 0
  fi
  if grep -q '{% load static %}' "$file" 2>/dev/null; then
    sed -i '1i{% load static %}' "$file" 2>/dev/null || true
  fi
  if grep -qi '</head>' "$file"; then
    sed -i 's|</head>|  <link rel="stylesheet" href="{% static '\''chart_patch/bookmap_below_chart.css'\'' %}" />\n  <script src="{% static '\''chart_patch/bookmap_layout.js'\'' %}" defer></script>\n</head>|' "$file"
    echo "  patched template: $file"
  fi
}

echo "==> Copying patch assets → $PATCH_DEST"
echo "==> Injecting into HTML/templates ..."

while IFS= read -r html; do
  _inject_html "$html"
done < <(find "$CHART_ROOT" -path '*/node_modules/*' -prune -o -path '*/.venv/*' -prune -o -name 'index.html' -print 2>/dev/null | head -20)

while IFS= read -r tpl; do
  _inject_template "$tpl"
done < <(find "$CHART_ROOT" -path '*/templates/*' -name '*.html' -print 2>/dev/null | head -20)

# Also patch staticfiles (Django collectstatic output)
if [[ -d "$CHART_ROOT/staticfiles" ]]; then
  mkdir -p "$CHART_ROOT/staticfiles/chart_patch"
  cp "$PATCH_SRC/bookmap_below_chart.css" "$CHART_ROOT/staticfiles/chart_patch/"
  cp "$PATCH_SRC/bookmap_layout.js" "$CHART_ROOT/staticfiles/chart_patch/"
  _inject_html "$CHART_ROOT/staticfiles/index.html"
fi

echo ""
echo "Done. Restart OpenTrader and hard-refresh (Ctrl+Shift+R):"
echo "  bash scripts/run_my_old_app.sh"
echo ""
echo "Bookmap Order Flow should appear BELOW the chart."
