#!/usr/bin/env bash
# Merge git engine into YOUR old Open Trader app at /home/heinz/opentrade-app
# Keeps your original chart UI + adds MT5 auto-sync, backtest, journal, optimizer API.
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

# Copy engine modules into old app (merge — do not delete your existing MT5/server code)
for dir in trading opentrade opentrader scripts; do
  if [[ -d "$ENGINE_ROOT/$dir" ]]; then
    echo "→ Sync $dir/ (merge, keeps existing files)"
    mkdir -p "$OLD_APP/$dir"
    rsync -a "$ENGINE_ROOT/$dir/" "$OLD_APP/$dir/"
  fi
done

for f in requirements.txt requirements-mt5.txt requirements-dev.txt install_and_run.sh .env.blackbull.example; do
  [[ -f "$ENGINE_ROOT/$f" ]] && cp "$ENGINE_ROOT/$f" "$OLD_APP/$f"
done

mkdir -p "$OLD_APP/trading_data/blackbull_import"

# .env for old app location
ENV_FILE="$OLD_APP/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENGINE_ROOT/.env.blackbull.example" "$ENV_FILE"
  echo "Created $ENV_FILE — edit MT5_LOGIN, MT5_PASSWORD, MT5_SERVER"
fi

# Ensure OPENTRADER_OLD_APP is set in .env
if ! grep -q "^OPENTRADER_OLD_APP=" "$ENV_FILE" 2>/dev/null; then
  echo "OPENTRADER_OLD_APP=$OLD_APP" >> "$ENV_FILE"
fi

# Old app already runs MT5 — don't start a second autosync unless you opt in
if ! grep -q "^MT5_AUTO_SYNC=" "$ENV_FILE" 2>/dev/null; then
  echo "MT5_AUTO_SYNC=0" >> "$ENV_FILE"
fi

# Launcher in old app folder
cat > "$OLD_APP/run.sh" << 'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENTRADER_OLD_APP="$(pwd)"
export PORT="${PORT:-8010}"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
bash install_and_run.sh
LAUNCHER
chmod +x "$OLD_APP/run.sh"

echo ""
echo "=== Done ==="
echo ""
echo "Your old chart UI at:  $OLD_APP"
echo "Engine + API synced."
echo ""
echo "Start (one command, port 8010):"
echo "  cd $OLD_APP"
echo "  bash run.sh"
echo ""
echo "Or with force restart:"
echo "  cd $OLD_APP && FORCE=1 bash run.sh"
echo ""
echo "This serves YOUR old index.html + new API (backtest, journal, optimizer,"
echo "bookmap). Your existing MT5 / BlackBull setup is unchanged (MT5_AUTO_SYNC=0)."
