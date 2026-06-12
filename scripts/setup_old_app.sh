#!/usr/bin/env bash
# One-command setup: backup UI, merge engine, restore UI if missing, install deps, start app.
#
# Usage:
#   bash scripts/setup_old_app.sh
#   bash scripts/setup_old_app.sh /home/heinz/opentrade-app
#   FORCE=1 bash scripts/setup_old_app.sh /home/heinz/opentrade-app
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLD_APP="${1:-${OPENTRADER_OLD_APP:-/home/heinz/opentrade-app}}"

echo "=============================================="
echo " Open Trader — full setup for your old app"
echo "=============================================="
echo "Engine:   $ENGINE_ROOT"
echo "Old app:  $OLD_APP"
echo ""

if [[ ! -d "$OLD_APP" ]]; then
  echo "Creating $OLD_APP ..."
  mkdir -p "$OLD_APP"
fi

# 1) Backup UI before any merge
bash "$ENGINE_ROOT/scripts/backup_old_ui.sh" "$OLD_APP"

# 2) Merge engine (never overwrites your UI static)
bash "$ENGINE_ROOT/scripts/integrate_old_app.sh" "$OLD_APP"

# 3) Restore UI if index.html is missing or was replaced by git UI
_has_ui() {
  local base="$1"
  [[ -f "$base/index.html" ]] && return 0
  [[ -f "$base/static/index.html" ]] && return 0
  [[ -f "$base/public/index.html" ]] && return 0
  [[ -f "$base/dist/index.html" ]] && return 0
  [[ -f "$base/frontend/index.html" ]] && return 0
  return 1
}

if ! _has_ui "$OLD_APP"; then
  echo ""
  echo "==> No chart UI found — restoring from backup ..."
  if [[ -d "$OLD_APP/.opentrader_ui_backup/latest" ]]; then
    bash "$ENGINE_ROOT/scripts/restore_old_ui.sh" "$OLD_APP"
  else
    echo "WARNING: No backup and no index.html in $OLD_APP"
    echo "Your original chart files may be elsewhere. Set in .env:"
    echo "  OPENTRADER_UI_INDEX=/path/to/your/index.html"
  fi
fi

# 4) Install + run
echo ""
echo "==> Installing dependencies and starting server ..."
cd "$OLD_APP"
export OPENTRADER_OLD_APP="$(pwd)"
export PORT="${PORT:-8010}"
FORCE="${FORCE:-1}" bash run.sh
