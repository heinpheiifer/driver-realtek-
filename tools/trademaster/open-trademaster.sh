#!/usr/bin/env bash
# Open TradeMaster (Jupyter Lab + optional Ray dashboard) on heinz-Predator.
# Usage:  bash tools/trademaster/open-trademaster.sh
set -euo pipefail

TM="${TRADEMASTER_ROOT:-$HOME/TradeMaster}"
PORT="${TRADEMASTER_JUPYTER_PORT:-8888}"

if [[ ! -d "$TM" ]]; then
  echo "TradeMaster not found at: $TM"
  echo "Set TRADEMASTER_ROOT or clone: git clone https://github.com/TradeMaster-NTU/TradeMaster.git ~/TradeMaster"
  exit 1
fi

cd "$TM"

if [[ ! -x .venv/bin/python ]]; then
  echo "No .venv in $TM — create one first:"
  echo "  cd $TM && python3 -m venv .venv && .venv/bin/pip install -e . jupyterlab"
  exit 1
fi

PY="$TM/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "No .venv in $TM — create one first:"
  echo "  cd $TM && python3 -m venv .venv && .venv/bin/pip install -e . jupyterlab"
  exit 1
fi

if ! "$PY" -m jupyter --version >/dev/null 2>&1; then
  echo "Installing jupyterlab in TradeMaster venv..."
  "$PY" -m pip install -U pip jupyterlab
fi

echo "══════════════════════════════════════════════════"
echo "  TradeMaster — $TM"
echo "══════════════════════════════════════════════════"
echo ""
echo "  Tutorials:  $TM/tutorial/"
echo "  DeepScalper auto-tune:  scripts/auto_tune_deepscalper.py"
echo ""
echo "  Already running?"
pgrep -af "TradeMaster|auto_tune_deepscalper|jupyter.*$PORT" 2>/dev/null | sed 's/^/    /' || echo "    (none)"
echo ""

if pgrep -f "jupyter.*--port=${PORT}" >/dev/null 2>&1; then
  echo "Jupyter already on port $PORT — open:"
  echo "  http://127.0.0.1:${PORT}/lab"
  echo ""
  "$PY" -m jupyter lab list 2>/dev/null | sed 's/^/  /' || true
  exit 0
fi

echo "Starting Jupyter Lab on http://127.0.0.1:${PORT}/lab"
echo "  (Ctrl+C to stop)"
echo ""
exec "$PY" -m jupyter lab --port="$PORT" --ip=127.0.0.1 --no-browser
