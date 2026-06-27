#!/usr/bin/env bash
# Install numpy in Wine Python + restart bridge (fixes order_send/modify "np is not defined").
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^MT5_WINE_ ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    export "$key=$value"
  done < <(grep -E '^MT5_WINE_' .env)
fi

WINE_PYTHON="${MT5_WINE_PYTHON:-wine python}"
WINE_PYTHON="${WINE_PYTHON//\$HOME/$HOME}"
read -ra WINE_PY_CMD <<< "$WINE_PYTHON"

echo "==> Installing numpy + MT5 packages in Wine Python"
"${WINE_PY_CMD[@]}" -m pip install --upgrade pip
"${WINE_PY_CMD[@]}" -m pip install numpy MetaTrader5 mt5linux

echo ""
echo "==> Restarting Wine MT5 bridge"
./scripts/stop-wine-mt5linux.sh 2>/dev/null || true
./scripts/ensure-wine-bridge.sh || ./scripts/start-wine-mt5linux.sh

echo ""
echo "Done. Restart main.py and test a small ETHUSD trade."
