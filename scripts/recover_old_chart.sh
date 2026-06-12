#!/usr/bin/env bash
# Search your whole home folder for the original Open Trader chart UI.
set -euo pipefail

HOME_DIR="${1:-$HOME}"

echo "=============================================="
echo " Search home for original Open Trader chart"
echo "=============================================="
echo "Searching: $HOME_DIR"
echo ""

SEARCH_DIRS=(
  "$HOME_DIR/opentrade-app"
  "$HOME_DIR/opentrader-app"
  "$HOME_DIR/OpenTrader"
  "$HOME_DIR/open-trader"
  "$HOME_DIR/trading"
  "$HOME_DIR/charts"
  "$HOME_DIR/Desktop"
  "$HOME_DIR/Documents"
  "$HOME_DIR/Downloads"
)

echo "--- Folders that exist ---"
for d in "${SEARCH_DIRS[@]}"; do
  [[ -d "$d" ]] && echo "  $d"
done

echo ""
echo "=== YOUR REAL CHART IS PROBABLY HERE ==="
for f in \
  "$HOME_DIR/OpenTrader/frontend/dist/index.html" \
  "$HOME_DIR/OpenTrader/frontend/index.html" \
  "$HOME_DIR/OpenTrader/staticfiles/index.html"; do
  [[ -f "$f" ]] && echo "  ★★ $f  ← USE THIS"
done

echo ""
echo "--- HTML with OLD chart markers (heikin / drawing / lightweight-charts) ---"
FOUND=0
while IFS= read -r f; do
  case "$f" in
    *missing_old_ui*|*/.mt5/*|*/Python311/Doc/*|*/idlelib/*) continue ;;
  esac
  if grep -qiE 'heikin|drawing|lightweight-charts|LightweightCharts' "$f" 2>/dev/null && \
     ! grep -q 'runBacktestBtn' "$f" 2>/dev/null; then
    echo "  ★ $f"
    FOUND=$((FOUND + 1))
  fi
done < <(find "$HOME_DIR/OpenTrader" "$HOME_DIR/opentrade-app" \
  -maxdepth 8 \
  \( -path '*/.venv/*' -o -path '*/node_modules/*' -o -path '*/.git/*' \) -prune -o \
  -name '*.html' -print 2>/dev/null)

if [[ "$FOUND" -eq 0 ]]; then
  echo "  (none found)"
fi

echo ""
echo "--- ALL index.html under home (max depth 6) ---"
find "$HOME_DIR" -maxdepth 6 -name 'index.html' 2>/dev/null | grep -v node_modules | grep -v .venv | head -30

echo ""
echo "--- Backups in opentrade-app ---"
BACKUP="$HOME_DIR/opentrade-app/.opentrader_ui_backup"
if [[ -d "$BACKUP" ]]; then
  ls -la "$BACKUP"
  for b in "$BACKUP"/*/; do
    [[ -d "$b" ]] || continue
    echo "  backup $(basename "$b"):"
    find "$b" -name '*.html' 2>/dev/null | head -5 | sed 's/^/    /'
  done
else
  echo "  (no .opentrader_ui_backup)"
fi

echo ""
echo "--- Python servers (old app may not use index.html) ---"
grep -rl --include='*.py' -E 'FastAPI|Flask|uvicorn|8010' \
  "$HOME_DIR/opentrade-app" "$HOME_DIR/opentrader-app" 2>/dev/null | head -15 || true

echo ""
if [[ "$FOUND" -gt 0 ]] || [[ -f "$HOME_DIR/OpenTrader/frontend/dist/index.html" ]]; then
  echo ""
  echo "NEXT (one command):"
  echo "  cd ~/opentrader-app && FORCE=1 bash scripts/connect_opentrader_chart.sh"
  echo ""
  echo "Or manual .env in /home/heinz/opentrade-app:"
  echo "  OPENTRADER_USE_OLD_UI=1"
  echo "  OPENTRADER_OLD_APP=/home/heinz/OpenTrader"
  echo "  OPENTRADER_UI_INDEX=/home/heinz/OpenTrader/frontend/dist/index.html"
else
  echo "No old chart HTML found on this PC."
  echo "Check: another machine, USB backup, Windows partition, or email/cloud zip of the old app."
  echo "Tell us which folder you used BEFORE integrate — it may not be opentrade-app."
fi
