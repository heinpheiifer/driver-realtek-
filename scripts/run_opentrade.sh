#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "uvicorn not found — run: bash scripts/setup_opentrade.sh"
  exit 1
fi

if [[ ! -f trading_data/eurusd_m1.csv ]]; then
  python3 -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
fi

echo "Starting OpenTrade at http://127.0.0.1:8010"
exec python3 -m uvicorn opentrade.main:app --host 127.0.0.1 --port 8010
