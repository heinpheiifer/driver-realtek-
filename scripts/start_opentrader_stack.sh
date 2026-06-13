#!/usr/bin/env bash
# Full stack: Django MT5 backend + chart engine on 8010 + optional MT5 bridge
#
# Usage:
#   bash scripts/start_opentrader_stack.sh
#   FORCE=1 bash scripts/start_opentrader_stack.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
ENGINE_DIR="${2:-/home/heinz/opentrade-app}"
DJANGO_PORT="${DJANGO_PORT:-8000}"

echo "=============================================="
echo " OpenTrader full stack (chart + BlackBull)"
echo "=============================================="

# 1) Django backend (original MT5 API)
bash "$ENGINE_ROOT/scripts/start_opentrader_django.sh" "$CHART_ROOT" || true

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

if [[ -f "$CHART_ROOT/manage.py" ]] || [[ -f "$CHART_ROOT/backend/manage.py" ]]; then
  _set_env "OPENTRADER_BACKEND_URL" "http://127.0.0.1:${DJANGO_PORT}"
  _set_env "OPENTRADER_DJANGO_PROXY" "1"
  echo "==> Market API proxied to Django :${DJANGO_PORT} (original setup)"
else
  sed -i '/^OPENTRADER_BACKEND_URL=/d' "$ENV_FILE" 2>/dev/null || true
  echo "==> No Django — will try MT5 bridge for BlackBull data"
  bash "$ENGINE_ROOT/scripts/start_blackbull_bridge.sh" "$ENGINE_DIR" || true
fi

# 2) Chart + engine on 8010
bash "$ENGINE_ROOT/scripts/connect_opentrader_chart.sh" "$CHART_ROOT" "$ENGINE_DIR"
