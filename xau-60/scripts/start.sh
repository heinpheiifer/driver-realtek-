#!/usr/bin/env bash
# Start XAU-60 dashboard on port 8010
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

export STREAMLIT_SERVER_PORT=8010
export STREAMLIT_SERVER_ADDRESS=0.0.0.0

echo "Starting XAU-60 MT5 Trading Bot UI on http://localhost:8010"
echo "Press Ctrl+C to stop."
echo ""

exec .venv/bin/streamlit run ui/app.py \
  --server.port=8010 \
  --server.address=0.0.0.0 \
  --browser.gatherUsageStats=false
