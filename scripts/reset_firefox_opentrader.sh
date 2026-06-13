#!/usr/bin/env bash
# Full reset for Firefox freeze / blank chart — remove patches, purge cache files, start Django.
#
# Usage:
#   bash scripts/reset_firefox_opentrader.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"

echo "=============================================="
echo " Firefox reset — OpenTrader"
echo "=============================================="

echo ""
echo "==> 1. Remove ALL layout patches + delete chart_patch JS/CSS"
PURGE=1 bash "$ENGINE_ROOT/scripts/unpatch_bookmap.sh" "$CHART_ROOT"

echo ""
echo "==> 2. Stop wrong servers (8010, 8011)"
PORT=8010 bash "$ENGINE_ROOT/scripts/stop_opentrader.sh" 2>/dev/null || true
fuser -k 8011/tcp 2>/dev/null || true
pkill -f "uvicorn opentrader.main" 2>/dev/null || true
pkill -f "manage.py runserver" 2>/dev/null || true
sleep 1

echo ""
echo "==> 3. Start YOUR Django chart (port 8010 only)"
export OPENTRADER_SKIP_BOOKMAP_PATCH=1
export OPENTRADER_BOOKMAP_BELOW=0
export OPENTRADER_PATCH_DJANGO=0
exec bash "$ENGINE_ROOT/scripts/start_opentrader_simple.sh" "$CHART_ROOT"
