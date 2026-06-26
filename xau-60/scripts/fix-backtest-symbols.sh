#!/usr/bin/env bash
# Force-sync ui/views/backtest.py from GitHub (fixes _CHART_SYMBOLS NameError)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BRANCH="${1:-cursor/xau60-mt5-setup-dc2c}"

echo "==> Fetching origin/$BRANCH ..."
git fetch origin "$BRANCH"

echo "==> Restoring ui/views/backtest.py from origin/$BRANCH ..."
git checkout "origin/$BRANCH" -- ui/views/backtest.py

if grep -q '_CHART_SYMBOLS' ui/views/backtest.py && ! grep -q '_CHART_SYMBOLS = ' ui/views/backtest.py; then
  echo "ERROR: backtest.py still broken — contact support"
  exit 1
fi

echo "OK — restart UI: ./scripts/stop-ui.sh && ./scripts/start.sh"
