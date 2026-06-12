#!/usr/bin/env bash
# Stop any running OpenTrader/OpenTrade server and start fresh on port 8010.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash "$ROOT/scripts/stop_opentrader.sh"
echo "==> Starting fresh ..."
exec bash install_and_run.sh
