#!/usr/bin/env bash
# Full start: sudo deps + OpenTrader Django on :8010
# Password file (NEVER commit): ~/opentrader-app/.opentrader_sudo_pass
#
# Usage:
#   echo 'YOUR_SUDO_PASSWORD' > ~/opentrader-app/.opentrader_sudo_pass
#   chmod 600 ~/opentrader-app/.opentrader_sudo_pass
#   bash scripts/opentrader_start_all.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PASS_FILE="${OPENTRADER_SUDO_PASS_FILE:-$ENGINE_ROOT/.opentrader_sudo_pass}"

_sudo() {
  if sudo -n true 2>/dev/null; then
    sudo "$@"
    return
  fi
  if [[ -f "$PASS_FILE" ]]; then
    echo "==> Using sudo password from $PASS_FILE"
    sudo -S "$@" <<< "$(tr -d '\r\n' < "$PASS_FILE")"
    return
  fi
  echo "ERROR: sudo needs a password."
  echo "Create: echo 'YOUR_PASSWORD' > $PASS_FILE && chmod 600 $PASS_FILE"
  exit 1
}

echo "=============================================="
echo " OpenTrader — full install + start"
echo "=============================================="

echo "==> System packages (python3-venv, pip, curl) ..."
_sudo apt-get update -qq
_sudo apt-get install -y python3 python3-pip python3-venv curl

bash "$ENGINE_ROOT/scripts/restore_django_settings.sh" "$CHART_ROOT" 2>/dev/null || true
bash "$ENGINE_ROOT/scripts/unpatch_bookmap.sh" "$CHART_ROOT" 2>/dev/null || true
bash "$ENGINE_ROOT/scripts/patch_django_frontend.sh" "$CHART_ROOT" 2>/dev/null || true

fuser -k 8010/tcp 8011/tcp 2>/dev/null || true
pkill -f "manage.py runserver" 2>/dev/null || true
pkill -f "uvicorn opentrader.main" 2>/dev/null || true
sleep 1

exec bash "$ENGINE_ROOT/scripts/opentrader_go.sh" "$CHART_ROOT"
