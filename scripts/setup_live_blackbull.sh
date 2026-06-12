#!/usr/bin/env bash
# Live BlackBull data on Linux (Wine MT5) — copy EA + enable auto-import
#
# Usage:
#   bash ~/opentrader-app/scripts/setup_live_blackbull.sh
#   bash ~/opentrader-app/scripts/setup_live_blackbull.sh /home/heinz/opentrade-app
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="${1:-/home/heinz/opentrade-app}"

echo "=============================================="
echo " Live BlackBull setup (Linux + Wine MT5)"
echo "=============================================="

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

_set_env "MT5_WINE_SYNC" "1"
_set_env "MT5_SYNC_INTERVAL" "30"
_set_env "OPENTRADER_DJANGO_PROXY" "0"
sed -i '/^OPENTRADER_BACKEND_URL=/d' "$ENV_FILE" 2>/dev/null || true

# Copy EAs into Wine MT5
EA_COPIED=0
for mql5 in $(find "$HOME/.mt5/drive_c" -type d -name MQL5 2>/dev/null); do
  mkdir -p "$mql5/Experts" "$mql5/Scripts"
  cp "$ENGINE_ROOT/scripts/BlackBullLivePush.mq5" "$mql5/Experts/"
  cp "$ENGINE_ROOT/scripts/BlackBullExportToOpenTrader.mq5" "$mql5/Scripts/"
  EA_COPIED=1
  echo "==> Installed EAs in: $mql5"
done

if [[ "$EA_COPIED" -eq 0 ]]; then
  echo ""
  echo "WARNING: Wine MT5 not found at ~/.mt5/drive_c"
  echo "Install BlackBull MT5 for Linux first, then re-run this script."
fi

# Import any existing CSV exports
cd "$ENGINE_DIR"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo ""
echo "==> Importing Wine MT5 CSV exports (if any) ..."
python3 -c "
from trading.blackbull_mt5 import sync_wine_mt5_exports, find_wine_mt5_files_dirs
r = sync_wine_mt5_exports()
print('Imported', r.get('count', 0), 'file(s)')
for s in r.get('sources', []):
    print('  from', s)
if not find_wine_mt5_files_dirs():
    print('No MQL5/Files folder found yet — start MT5 once first.')
"

echo ""
echo "=============================================="
echo " IN MT5 (BlackBull, must be running):"
echo "=============================================="
echo "1. Tools → Options → Expert Advisors"
echo "   ✓ Allow algorithmic trading"
echo "   ✓ Allow WebRequest for: http://127.0.0.1:8010"
echo ""
echo "2. Navigator → Expert Advisors → BlackBullLivePush"
echo "   Drag onto XRPUSD chart (or any chart)"
echo "   Inputs: InpSymbols=XRPUSD,EURUSD,BTCUSD"
echo "            InpOpenTraderUrl=http://127.0.0.1:8010/api/market/blackbull/import"
echo ""
echo "3. Restart chart engine:"
echo "   cd $ENGINE_DIR && bash scripts/stop_opentrader.sh && FORCE=1 bash run.sh"
echo ""
echo "4. Test live BlackBull:"
echo "   curl -s 'http://127.0.0.1:8010/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull' | grep -E 'fallback|source|count'"
echo "   (fallback should be false, source should contain blackbull)"
echo "=============================================="
