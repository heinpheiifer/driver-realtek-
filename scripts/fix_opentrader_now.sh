#!/usr/bin/env bash
# ONE COMMAND to fix and restart your OpenTrader chart app.
#
# Usage:
#   bash ~/opentrader-app/scripts/fix_opentrader_now.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
ENGINE_DIR="${2:-/home/heinz/opentrade-app}"

echo "=============================================="
echo " FIX OpenTrader — restore working chart"
echo "=============================================="
echo "Git engine:  $ENGINE_ROOT"
echo "Chart UI:    $CHART_ROOT"
echo "Run folder:  $ENGINE_DIR"
echo ""

if [[ -d "$ENGINE_ROOT/.git" ]]; then
  echo "==> Updating engine code ..."
  cd "$ENGINE_ROOT"
  git pull --ff-only 2>/dev/null || git pull 2>/dev/null || true
fi

mkdir -p "$ENGINE_DIR"
echo "==> Syncing engine into $ENGINE_DIR ..."
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

# Chart paths
CHART_INDEX=""
if [[ -d "$CHART_ROOT" ]]; then
  for rel in frontend/dist/index.html frontend/index.html staticfiles/index.html static/index.html; do
    if [[ -f "$CHART_ROOT/$rel" ]] && ! grep -q 'runBacktestBtn' "$CHART_ROOT/$rel" 2>/dev/null; then
      CHART_INDEX="$CHART_ROOT/$rel"
      break
    fi
  done
fi

_set_env "OPENTRADER_USE_OLD_UI" "1"
_set_env "OPENTRADER_OLD_APP" "$CHART_ROOT"
_set_env "OPENTRADER_DJANGO_PROXY" "0"
_set_env "MT5_AUTO_SYNC" "0"
_set_env "MT5_WINE_SYNC" "1"
sed -i '/^OPENTRADER_USE_NEW_UI=/d' "$ENV_FILE" 2>/dev/null || true
sed -i '/^OPENTRADER_BACKEND_URL=/d' "$ENV_FILE" 2>/dev/null || true

if [[ -n "$CHART_INDEX" ]]; then
  _set_env "OPENTRADER_UI_INDEX" "$CHART_INDEX"
  _set_env "OPENTRADER_CHART_ROOT" "$CHART_ROOT"
  echo "==> Chart: $CHART_INDEX"
else
  echo "==> Warning: chart not found in $CHART_ROOT — using engine defaults"
fi

echo ""
echo "==> Stopping old server ..."
bash "$ENGINE_DIR/scripts/stop_opentrader.sh" 2>/dev/null || true

echo "==> Starting chart app on http://127.0.0.1:8010 ..."
cd "$ENGINE_DIR"
export OPENTRADER_USE_OLD_UI=1
export OPENTRADER_OLD_APP="$CHART_ROOT"
export OPENTRADER_DJANGO_PROXY=0
export PORT="${PORT:-8010}"
nohup bash run.sh >>"$ENGINE_DIR/.opentrader_server.log" 2>&1 &
echo $! >"$ENGINE_DIR/.opentrader_server.pid"
sleep 5

echo ""
echo "==> Verifying API ..."
FAIL=0
check() {
  local url="$1" expect="$2"
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo 000)"
  if [[ "$code" == "$expect" ]]; then
    echo "  OK  HTTP $code  $url"
  else
    echo "  FAIL  HTTP $code (want $expect)  $url"
    FAIL=1
  fi
}

check "http://127.0.0.1:8010/" "200"
check "http://127.0.0.1:8010/api/health" "200"
check "http://127.0.0.1:8010/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull" "200"
check "http://127.0.0.1:8010/api/symbols/?source=blackbull&q=btc&limit=300" "200"
check "http://127.0.0.1:8010/api/mt5/status/" "200"

HEALTH="$(curl -sf http://127.0.0.1:8010/api/health 2>/dev/null || echo '{}')"
if echo "$HEALTH" | grep -q "2025-06-offline-seeds"; then
  echo "  OK  engine_build=2025-06-offline-seeds"
else
  echo "  WARN  old engine still running — stop other servers on port 8010"
  FAIL=1
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "=============================================="
  echo " FIXED — open http://127.0.0.1:8010"
  echo ""
  echo " For LIVE BlackBull data (not yahoo/synthetic):"
  echo "   bash $ENGINE_ROOT/scripts/setup_live_blackbull.sh $ENGINE_DIR"
  echo "=============================================="
else
  echo "Some checks failed. See: tail -50 $ENGINE_DIR/.opentrader_server.log"
  echo "Retry: cd $ENGINE_DIR && FORCE=1 bash run.sh"
  exit 1
fi
