#!/usr/bin/env bash
# Start Wine MT5 bridge + XAU-60 dashboard (recommended daily launcher).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "========================================"
echo " XAU-60 — Wine MT5 + Dashboard"
echo "========================================"
echo ""
echo "Step 1: Make sure MetaTrader 5 is OPEN in Wine"
echo "        Logged into 517035 @ BlackBullMarkets-Live"
echo ""
read -r -p "Press Enter when MT5 is open and logged in..."

echo ""
echo "Step 2: Starting Wine MT5 bridge..."
echo "        (This terminal must stay open for the bridge)"
echo ""

exec "$ROOT/scripts/start-wine-mt5linux.sh"
