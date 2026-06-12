#!/usr/bin/env bash
# Restore original Open Trader UI from .opentrader_ui_backup/latest
set -euo pipefail

OLD_APP="${1:-${OPENTRADER_OLD_APP:-/home/heinz/opentrade-app}}"
BACKUP="${2:-$OLD_APP/.opentrader_ui_backup/latest}"

if [[ ! -d "$OLD_APP" ]]; then
  echo "Old app folder not found: $OLD_APP"
  exit 1
fi

if [[ ! -d "$BACKUP" ]]; then
  echo "No UI backup found at: $BACKUP"
  echo "Run: bash scripts/backup_old_ui.sh $OLD_APP"
  exit 1
fi

echo "Restoring UI from $BACKUP → $OLD_APP"

restore_item() {
  local name="$1"
  local src="$BACKUP/$name"
  if [[ -e "$src" ]]; then
    rm -rf "$OLD_APP/$name"
    cp -a "$src" "$OLD_APP/$name"
    echo "  ✓ restored $name"
  fi
}

for item in index.html static public dist frontend web ui client templates assets js css; do
  restore_item "$item"
done

if [[ -d "$BACKUP/opentrader/static" ]]; then
  mkdir -p "$OLD_APP/opentrader"
  rm -rf "$OLD_APP/opentrader/static"
  cp -a "$BACKUP/opentrader/static" "$OLD_APP/opentrader/static"
  echo "  ✓ restored opentrader/static"
fi

echo ""
echo "Done. Restart: cd $OLD_APP && FORCE=1 bash run.sh"
