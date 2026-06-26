#!/usr/bin/env bash
# Start mt5linux RPyC server inside Wine (same laptop as XAU-60 UI).
#
# Prerequisites:
#   - MT5 terminal running in Wine (BlackBull logged in)
#   - Windows Python in Wine with: pip install MetaTrader5 mt5linux
#
# Usage:
#   ./scripts/start-wine-mt5linux.sh
#   MT5_WINE_PYTHON="wine /path/to/python.exe" ./scripts/start-wine-mt5linux.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

HOST="${MT5_WINE_HOST:-0.0.0.0}"
PORT="${MT5_WINE_PORT:-18812}"
WINE_PYTHON="${MT5_WINE_PYTHON:-wine python}"

# Expand $HOME in .env paths
WINE_PYTHON="${WINE_PYTHON//\$HOME/$HOME}"

echo "==> XAU-60 Wine MT5 bridge (mt5linux RPyC)"
echo "    Host: $HOST  Port: $PORT"
echo ""
echo "Before continuing:"
echo "  1. Open MetaTrader 5 in Wine and log into BlackBull"
echo "  2. In Wine Python: pip install MetaTrader5 mt5linux"
echo ""
echo "Linux .env should include:"
echo "  MT5_WINE_ENABLED=true"
echo "  MT5_WINE_HOST=localhost"
echo "  MT5_WINE_PORT=$PORT"
echo ""

exec $WINE_PYTHON -m mt5linux --host "$HOST" -p "$PORT"
