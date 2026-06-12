#!/usr/bin/env bash
# Connect engine (opentrade-app) to YOUR real chart in ~/OpenTrader
#
# Usage:
#   bash scripts/connect_opentrader_chart.sh
#   FORCE=1 bash scripts/connect_opentrader_chart.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
ENGINE_DIR="${2:-/home/heinz/opentrade-app}"

echo "=============================================="
echo " Connect OpenTrader chart → engine"
echo "=============================================="
echo "Chart UI:  $CHART_ROOT"
echo "Engine:    $ENGINE_DIR"
echo ""

if [[ ! -d "$CHART_ROOT" ]]; then
  echo "ERROR: Chart folder not found: $CHART_ROOT"
  exit 1
fi

# Pick best index.html (production build first)
CHART_INDEX=""
for rel in frontend/dist/index.html frontend/index.html staticfiles/index.html static/index.html; do
  if [[ -f "$CHART_ROOT/$rel" ]] && ! grep -q 'runBacktestBtn' "$CHART_ROOT/$rel" 2>/dev/null; then
    CHART_INDEX="$CHART_ROOT/$rel"
    echo "==> Found chart: $CHART_INDEX"
    break
  fi
done

if [[ -z "$CHART_INDEX" ]]; then
  echo "ERROR: No chart index.html in $CHART_ROOT"
  echo "Try: ls -la $CHART_ROOT/frontend/"
  exit 1
fi

mkdir -p "$ENGINE_DIR"
bash "$ENGINE_ROOT/scripts/integrate_old_app.sh" "$ENGINE_DIR"

ENV_FILE="$ENGINE_DIR/.env"
touch "$ENV_FILE"

_set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

_set_env "OPENTRADER_USE_OLD_UI" "1"
_set_env "OPENTRADER_OLD_APP" "$CHART_ROOT"
_set_env "OPENTRADER_UI_INDEX" "$CHART_INDEX"
_set_env "OPENTRADER_CHART_ROOT" "$CHART_ROOT"
_set_env "OPENTRADER_URL" "http://127.0.0.1:8010"
# MT5 via Django backend proxy or bridge — not engine autosync
_set_env "MT5_AUTO_SYNC" "0"
sed -i '/^OPENTRADER_USE_NEW_UI=/d' "$ENV_FILE" 2>/dev/null || true

echo ""
echo "==> .env configured:"
grep -E '^OPENTRADER_|^MT5_AUTO' "$ENV_FILE" || true

echo ""
echo "==> Starting (engine + your OpenTrader chart) ..."
cd "$ENGINE_DIR"
bash scripts/stop_opentrader.sh 2>/dev/null || true
export OPENTRADER_USE_OLD_UI=1
export OPENTRADER_OLD_APP="$CHART_ROOT"
export OPENTRADER_UI_INDEX="$CHART_INDEX"
export PORT="${PORT:-8010}"
FORCE="${FORCE:-1}" bash run.sh
