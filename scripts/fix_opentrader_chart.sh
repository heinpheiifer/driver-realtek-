#!/usr/bin/env bash
# Reset ~/OpenTrader chart: remove patches, start Django, print test URLs.
#
# Usage:
#   bash scripts/fix_opentrader_chart.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"

echo "==> Step 1: Remove Bookmap layout patches (restore original UI)"
bash "$ENGINE_ROOT/scripts/unpatch_bookmap.sh" "$CHART_ROOT"

echo ""
echo "==> Step 2: Diagnose"
bash "$ENGINE_ROOT/scripts/diagnose_opentrader.sh" "$CHART_ROOT"

echo ""
echo "==> Step 3: Start OpenTrader (no bookmap patch)"
export OPENTRADER_SKIP_BOOKMAP_PATCH=1
exec bash "$ENGINE_ROOT/scripts/run_my_old_app.sh" "$CHART_ROOT"
