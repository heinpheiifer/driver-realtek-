#!/usr/bin/env bash
# Patch ~/OpenTrader UI: Bookmap Order Flow below chart (not floating overlay).
#
# Usage:
#   bash scripts/patch_bookmap_below_chart.sh
#   bash scripts/patch_bookmap_below_chart.sh /home/heinz/OpenTrader
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PATCH_SRC="$ENGINE_ROOT/opentrader/chart_patches"

if [[ ! -d "$CHART_ROOT" ]]; then
  echo "ERROR: $CHART_ROOT not found"
  exit 1
fi

echo "==> Patching Bookmap layout: $CHART_ROOT"

_copy_patch_assets() {
  local dest="$1"
  mkdir -p "$dest"
  cp "$PATCH_SRC/bookmap_below_chart.css" "$dest/"
  cp "$PATCH_SRC/bookmap_layout.js" "$dest/"
  echo "  assets → $dest"
}

# Vite production build (most common for ~/OpenTrader)
_copy_patch_assets "$CHART_ROOT/frontend/dist/chart_patch"
_copy_patch_assets "$CHART_ROOT/static/chart_patch"
_copy_patch_assets "$CHART_ROOT/staticfiles/chart_patch"

_patch_prefix_for() {
  local file="$1"
  case "$file" in
    *"/frontend/dist/"*) echo "./chart_patch" ;;
    *"/staticfiles/"*) echo "/static/chart_patch" ;;
    *) echo "/static/chart_patch" ;;
  esac
}

_strip_old_patch() {
  local file="$1"
  sed -i \
    -e 's|[[:space:]]*<link rel="stylesheet" href="[^"]*chart_patch/bookmap_below_chart\.css"[^>]*/>[[:space:]]*||g' \
    -e 's|[[:space:]]*<script src="[^"]*chart_patch/bookmap_layout\.js"[^>]*></script>[[:space:]]*||g' \
    -e 's|[[:space:]]*<script src="[^"]*chart_patch/bookmap_layout\.js"[^>]*/>[[:space:]]*||g' \
    -e '/<style id="ot-bookmap-below-inline">/,/<\/style>/d' \
    "$file"
}

_patch_ok() {
  local file="$1"
  local prefix
  prefix="$(_patch_prefix_for "$file")"
  grep -q "${prefix}/bookmap_below_chart.css" "$file" 2>/dev/null && \
    grep -q "${prefix}/bookmap_layout.js" "$file" 2>/dev/null && \
    grep -q 'id="ot-bookmap-below-inline"' "$file" 2>/dev/null
}

_inject_html() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if grep -q "bookmap_below_chart.css" "$file" 2>/dev/null; then
    if _patch_ok "$file"; then
      echo "  already patched: $file"
      return 0
    fi
    echo "  re-patching (updating stale paths): $file"
    _strip_old_patch "$file"
  fi
  if ! grep -qi '</head>' "$file"; then
    return 0
  fi

  local prefix
  prefix="$(_patch_prefix_for "$file")"
  local inject
  inject="  <link rel=\"stylesheet\" href=\"${prefix}/bookmap_below_chart.css\" />\n"
  inject+="  <script src=\"${prefix}/bookmap_layout.js\" defer></script>\n"
  inject+="  <style id=\"ot-bookmap-below-inline\">"
  inject+="[data-ot-bookmap-below=\"1\"],.ot-bookmap-below,[class*=\"bookmap\"],[id*=\"bookmap\"]{"
  inject+="position:static!important;top:auto!important;right:auto!important;left:auto!important;"
  inject+="width:100%!important;max-width:none!important;order:2!important;min-height:220px!important;"
  inject+="border-top:1px solid #243044!important}.ot-chart-stack,.chart-area{display:flex!important;"
  inject+="flex-direction:column!important}</style>\n"

  sed -i "s|</head>|${inject}</head>|" "$file"
  echo "  patched: $file (${prefix})"
}

_inject_template() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if grep -q "bookmap_below_chart.css" "$file" 2>/dev/null; then
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

echo "==> Injecting into HTML/templates ..."

PRIORITY=(
  "$CHART_ROOT/frontend/dist/index.html"
  "$CHART_ROOT/frontend/index.html"
  "$CHART_ROOT/staticfiles/index.html"
  "$CHART_ROOT/static/index.html"
  "$CHART_ROOT/index.html"
)
for html in "${PRIORITY[@]}"; do
  _inject_html "$html"
done

while IFS= read -r html; do
  _inject_html "$html"
done < <(
  find "$CHART_ROOT" \
    -path '*/node_modules/*' -prune -o \
    -path '*/.venv/*' -prune -o \
    -name 'index.html' -print 2>/dev/null | head -30
)

while IFS= read -r tpl; do
  _inject_template "$tpl"
done < <(
  find "$CHART_ROOT" \
    -path '*/.venv/*' -prune -o \
    -path '*/node_modules/*' -prune -o \
    -path '*/site-packages/*' -prune -o \
    -path '*/templates/*' -name '*.html' -print 2>/dev/null | head -20
)

echo ""
echo "Done. Restart OpenTrader and hard-refresh (Ctrl+Shift+R):"
echo "  bash scripts/run_my_old_app.sh"
echo ""
echo "Bookmap Order Flow should appear BELOW the chart (full width, not top-right overlay)."
