#!/usr/bin/env bash
# Pull latest XAU-60 branch without losing local config edits.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="${1:-cursor/xau60-mt5-setup-dc2c}"

echo "==> Checking for local changes in config/..."
CHANGED=0
for path in config/settings.yaml config/strategies/*.yaml .env; do
  if [[ -f "$path" ]] && ! git diff --quiet -- "$path" 2>/dev/null; then
    CHANGED=1
    break
  fi
done

if [[ "$CHANGED" == "1" ]]; then
  echo "Stashing local config/.env (restore later with: git stash pop)"
  git stash push -m "xau60 local config $(date +%F-%H%M)" -- \
    config/settings.yaml config/strategies/ .env 2>/dev/null || \
  git stash push -m "xau60 local config $(date +%F-%H%M)" -- \
    config/settings.yaml config/strategies/
fi

echo "==> Pulling origin/$BRANCH ..."
git pull origin "$BRANCH"

echo ""
echo "Done. Next:"
echo "  .venv/bin/python scripts/debug-symbol.py ETHUSD"
echo "  .venv/bin/python scripts/test-trade.py --yes --close-after --symbol ETHUSD"
