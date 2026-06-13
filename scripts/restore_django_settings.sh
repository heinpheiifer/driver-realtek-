#!/usr/bin/env bash
# Restore opentrader/settings.py if git patches broke Django startup.
set -euo pipefail
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
cd "$CHART_ROOT"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git checkout -- opentrader/settings.py 2>/dev/null || true
  echo "Restored opentrader/settings.py from git (if it was modified)"
else
  echo "Not a git repo — skip settings restore"
fi
