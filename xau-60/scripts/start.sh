#!/usr/bin/env bash
# Start XAU-60 dashboard on port 8020 (8010 reserved for Tradenator)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Virtual env missing. Run: ./scripts/install-linux.sh"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — edit MT5 credentials before live trading."
fi

mkdir -p logs

# Auto-start Wine MT5 bridge when enabled in .env
if grep -qE '^MT5_WINE_ENABLED=(true|1|yes|on)' .env 2>/dev/null; then
  echo "Wine MT5 mode — ensuring bridge is running..."
  ./scripts/ensure-wine-bridge.sh || true
  echo ""
fi

export STREAMLIT_SERVER_PORT=8020
export STREAMLIT_SERVER_ADDRESS=0.0.0.0

echo "Starting XAU-60 MT5 Trading Bot UI on http://localhost:8020"
echo "(Port 8010 is reserved for Tradenator)"
echo "Press Ctrl+C to stop."
echo ""

exec .venv/bin/streamlit run ui/app.py \
  --server.port=8020 \
  --server.address=0.0.0.0 \
  --browser.gatherUsageStats=false
