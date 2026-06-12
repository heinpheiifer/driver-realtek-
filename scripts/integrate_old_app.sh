#!/usr/bin/env bash
# Merge git engine into YOUR old Open Trader app at /home/heinz/opentrade-app
# Keeps your original chart UI + adds backtest, journal, optimizer API.
#
# Usage:
#   bash scripts/integrate_old_app.sh
#   bash scripts/integrate_old_app.sh /home/heinz/opentrade-app
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLD_APP="${1:-${OPENTRADER_OLD_APP:-/home/heinz/opentrade-app}}"

echo "=== Integrate Open Trader engine into old app ==="
echo "Engine (git):  $ENGINE_ROOT"
echo "Old app UI:    $OLD_APP"
echo ""

if [[ ! -d "$OLD_APP" ]]; then
  echo "Old app folder not found: $OLD_APP"
  echo "Create it or pass path: bash scripts/integrate_old_app.sh /path/to/your/app"
  exit 1
fi

_sync_dir() {
  local src="$1"
  local dest="$2"
  local exclude="${3:-}"
  mkdir -p "$dest"
  if command -v rsync >/dev/null 2>&1; then
    if [[ -n "$exclude" ]]; then
      rsync -a --exclude "$exclude/" "$src/" "$dest/"
    else
      rsync -a "$src/" "$dest/"
    fi
    return
  fi
  shopt -s dotglob nullglob
  for item in "$src"/*; do
    local base
    base="$(basename "$item")"
    if [[ -n "$exclude" && "$base" == "$exclude" ]]; then
      continue
    fi
    cp -a "$item" "$dest/"
  done
}

# Always backup UI first (safe to run repeatedly)
bash "$ENGINE_ROOT/scripts/backup_old_ui.sh" "$OLD_APP" || true

# Copy engine modules — never overwrite user's chart UI in opentrader/static
for dir in trading opentrade scripts; do
  if [[ -d "$ENGINE_ROOT/$dir" ]]; then
    echo "→ Sync $dir/ (merge, keeps existing files)"
    _sync_dir "$ENGINE_ROOT/$dir" "$OLD_APP/$dir"
  fi
done

if [[ -d "$ENGINE_ROOT/opentrader" ]]; then
  echo "→ Sync opentrader/ (engine only — skips static/ to protect your chart UI)"
  _sync_dir "$ENGINE_ROOT/opentrader" "$OLD_APP/opentrader" "static"
  mkdir -p "$OLD_APP/opentrader/engine_static"
  _sync_dir "$ENGINE_ROOT/opentrader/static" "$OLD_APP/opentrader/engine_static"
fi

for f in requirements.txt requirements-mt5.txt requirements-dev.txt install_and_run.sh .env.blackbull.example; do
  [[ -f "$ENGINE_ROOT/$f" ]] && cp "$ENGINE_ROOT/$f" "$OLD_APP/$f"
done

mkdir -p "$OLD_APP/scripts"
cp "$ENGINE_ROOT/scripts/backup_old_ui.sh" "$OLD_APP/scripts/"
cp "$ENGINE_ROOT/scripts/restore_old_ui.sh" "$OLD_APP/scripts/"
cp "$ENGINE_ROOT/scripts/setup_old_app.sh" "$OLD_APP/scripts/"
cp "$ENGINE_ROOT/scripts/diagnose_old_app.sh" "$OLD_APP/scripts/"
cp "$ENGINE_ROOT/scripts/bring_back_old_app.sh" "$OLD_APP/scripts/"
cp "$ENGINE_ROOT/scripts/stop_opentrader.sh" "$OLD_APP/scripts/"
chmod +x "$OLD_APP/scripts/"*.sh

mkdir -p "$OLD_APP/trading_data/blackbull_import"

# .env for old app location
ENV_FILE="$OLD_APP/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENGINE_ROOT/.env.blackbull.example" "$ENV_FILE"
  echo "Created $ENV_FILE — edit MT5_LOGIN, MT5_PASSWORD, MT5_SERVER"
fi

if ! grep -q "^OPENTRADER_OLD_APP=" "$ENV_FILE" 2>/dev/null; then
  echo "OPENTRADER_OLD_APP=$OLD_APP" >> "$ENV_FILE"
fi

if ! grep -q "^OPENTRADER_USE_OLD_UI=" "$ENV_FILE" 2>/dev/null; then
  echo "OPENTRADER_USE_OLD_UI=1" >> "$ENV_FILE"
fi

if ! grep -q "^MT5_AUTO_SYNC=" "$ENV_FILE" 2>/dev/null; then
  echo "MT5_AUTO_SYNC=0" >> "$ENV_FILE"
fi

cat > "$OLD_APP/run.sh" << 'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENTRADER_USE_OLD_UI=1
export OPENTRADER_OLD_APP="$(pwd)"
export PORT="${PORT:-8010}"
bash install_and_run.sh
LAUNCHER
chmod +x "$OLD_APP/run.sh"

# Auto-restore if UI was wiped by a previous integrate
_has_ui() {
  [[ -f "$OLD_APP/index.html" ]] || [[ -f "$OLD_APP/static/index.html" ]] || \
  [[ -f "$OLD_APP/public/index.html" ]] || [[ -f "$OLD_APP/dist/index.html" ]]
}

if ! _has_ui && [[ -d "$OLD_APP/.opentrader_ui_backup/latest" ]]; then
  echo ""
  echo "==> Chart UI missing — restoring from backup ..."
  bash "$ENGINE_ROOT/scripts/restore_old_ui.sh" "$OLD_APP"
fi

echo ""
echo "=== Done ==="
echo ""
echo "Your old chart UI at:  $OLD_APP"
echo "Engine + API synced (your UI files were NOT overwritten)."
echo ""
echo "Start:"
echo "  cd $OLD_APP"
echo "  FORCE=1 bash run.sh"
echo ""
echo "Or full setup from git repo:"
echo "  bash scripts/setup_old_app.sh $OLD_APP"
echo ""
echo "If UI still wrong, restore manually:"
echo "  bash scripts/restore_old_ui.sh $OLD_APP"
