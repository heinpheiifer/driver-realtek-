#!/usr/bin/env bash
# Backup original Open Trader UI files before engine merge.
set -euo pipefail

OLD_APP="${1:-${OPENTRADER_OLD_APP:-/home/heinz/opentrade-app}}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_BASE="$OLD_APP/.opentrader_ui_backup"
BACKUP_DIR="$BACKUP_BASE/$STAMP"

if [[ ! -d "$OLD_APP" ]]; then
  echo "Old app folder not found: $OLD_APP"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
echo "Backing up UI → $BACKUP_DIR"

ITEMS=(
  index.html
  static
  public
  dist
  frontend
  web
  ui
  client
  templates
  assets
  js
  css
)

saved=0
for item in "${ITEMS[@]}"; do
  src="$OLD_APP/$item"
  if [[ -e "$src" ]]; then
    cp -a "$src" "$BACKUP_DIR/"
    echo "  ✓ $item"
    saved=$((saved + 1))
  fi
done

if [[ -d "$OLD_APP/opentrader/static" ]]; then
  mkdir -p "$BACKUP_DIR/opentrader"
  cp -a "$OLD_APP/opentrader/static" "$BACKUP_DIR/opentrader/"
  echo "  ✓ opentrader/static"
  saved=$((saved + 1))
fi

if [[ "$saved" -eq 0 ]]; then
  echo "  (nothing to backup — no UI files found yet)"
else
  ln -sfn "$STAMP" "$BACKUP_BASE/latest"
  echo "Latest backup: $BACKUP_BASE/latest"
fi
