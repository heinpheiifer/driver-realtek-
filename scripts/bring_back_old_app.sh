#!/usr/bin/env bash
# Bring back YOUR old Open Trader chart app at /home/heinz/opentrade-app
#
# Usage:
#   bash scripts/bring_back_old_app.sh
#   FORCE=1 bash scripts/bring_back_old_app.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLD_APP="${1:-/home/heinz/opentrade-app}"

echo "=============================================="
echo " Bring back your old Open Trader chart app"
echo "=============================================="
echo "Old app folder: $OLD_APP"
echo ""

if [[ ! -d "$OLD_APP" ]]; then
  echo "ERROR: $OLD_APP does not exist."
  exit 1
fi

bash "$ENGINE_ROOT/scripts/backup_old_ui.sh" "$OLD_APP" || true
bash "$ENGINE_ROOT/scripts/integrate_old_app.sh" "$OLD_APP"

# Restore if missing OR replaced by git engine UI
bash "$ENGINE_ROOT/scripts/find_old_chart.sh" "$OLD_APP" || true

_restore_needed() {
  local idx="$OLD_APP/static/index.html"
  if [[ ! -f "$OLD_APP/index.html" ]] && [[ ! -f "$idx" ]] && \
     [[ ! -f "$OLD_APP/public/index.html" ]]; then
    return 0
  fi
  if [[ -f "$idx" ]] && grep -q "btnBookmapToggle" "$idx" && grep -q "runBacktestBtn" "$idx"; then
    return 0
  fi
  return 1
}

if _restore_needed && [[ -d "$OLD_APP/.opentrader_ui_backup/latest" ]]; then
  echo ""
  echo "==> Restoring your original chart from backup ..."
  bash "$ENGINE_ROOT/scripts/restore_old_ui.sh" "$OLD_APP"
fi

# Ensure .env enables old UI
ENV_FILE="$OLD_APP/.env"
touch "$ENV_FILE"
for kv in "OPENTRADER_USE_OLD_UI=1" "OPENTRADER_OLD_APP=$OLD_APP" "MT5_AUTO_SYNC=0" "OPENTRADER_DJANGO_PROXY=0"; do
  key="${kv%%=*}"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${kv}|" "$ENV_FILE"
  else
    echo "$kv" >> "$ENV_FILE"
  fi
done

# Remove new-app-only flag if present
sed -i '/^OPENTRADER_USE_NEW_UI=/d' "$ENV_FILE" 2>/dev/null || true
sed -i '/^OPENTRADER_BACKEND_URL=/d' "$ENV_FILE" 2>/dev/null || true

echo ""
echo "==> Starting your old app ..."
cd "$OLD_APP"
export OPENTRADER_USE_OLD_UI=1
export OPENTRADER_OLD_APP="$(pwd)"
export PORT="${PORT:-8010}"
FORCE="${FORCE:-1}" bash run.sh
