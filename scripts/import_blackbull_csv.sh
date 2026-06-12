#!/usr/bin/env bash
# Copy MT5-exported BlackBull CSV into Open Trader import folder.
# Usage: bash scripts/import_blackbull_csv.sh /path/to/btcusd_m5.csv BTCUSD M5
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:?Usage: import_blackbull_csv.sh <csv-file> [SYMBOL] [TIMEFRAME]}"
SYMBOL="${2:-BTCUSD}"
TF="${3:-M5}"
DEST="$ROOT/trading_data/blackbull_import/${SYMBOL,,}_${TF,,}.csv"
mkdir -p "$(dirname "$DEST")"
cp "$SRC" "$DEST"
echo "Imported → $DEST"
echo "In Open Trader: select BlackBull → Load"
