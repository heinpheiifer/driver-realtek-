#!/usr/bin/env bash
# Find MetaTrader 5 terminal64.exe in Wine and save MT5_WINE_PATH to .env
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Searching for MT5 terminal in Wine..."
echo ""

.venv/bin/python << 'PY'
from utils.mt5_paths import (
    find_mt5_from_running_process,
    list_wine_mt5_terminals,
    find_wine_mt5_terminal,
)

running = find_mt5_from_running_process()
all_paths = list_wine_mt5_terminals()
best = find_wine_mt5_terminal()

print("Running MT5 process path:", running or "(MT5 not running)")
print("")
print("All terminal64.exe found:")
if all_paths:
    for p in all_paths:
        mark = " <-- best" if p == best else ""
        print(f"  {p}{mark}")
else:
    print("  (none — is MT5 installed in Wine?)")

print("")
if best:
    print(f"BEST_PATH={best}")
else:
    print("BEST_PATH=")
PY

BEST="$(.venv/bin/python -c "from utils.mt5_paths import find_wine_mt5_terminal; print(find_wine_mt5_terminal() or '')")"

if [[ -z "$BEST" ]]; then
  echo ""
  echo "Could not find terminal64.exe."
  echo "Install BlackBull MT5 in Wine, open it once, then re-run this script."
  exit 1
fi

echo ""
echo "Setting MT5_WINE_PATH in .env:"
echo "  $BEST"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

if grep -q '^MT5_WINE_PATH=' .env; then
  sed -i "s|^MT5_WINE_PATH=.*|MT5_WINE_PATH=$BEST|" .env
else
  echo "MT5_WINE_PATH=$BEST" >> .env
fi

if ! grep -q '^MT5_WINE_ENABLED=' .env; then
  echo "MT5_WINE_ENABLED=true" >> .env
fi

echo ""
echo "Done. Restart bridge and app:"
echo "  ./scripts/stop-wine-mt5linux.sh"
echo "  ./scripts/ensure-wine-bridge.sh"
echo "  ./scripts/start.sh"
