#!/usr/bin/env bash
# Fix Ollama PATH + research cron overlap for Tradenator 2.0 / OpenTrader.
#
# On heinz-Predator (after git pull):
#   cd ~/tradenator-xau60   # or wherever this repo lives
#   bash tools/opentrader/fix-all.sh
#
# Or copy tools/opentrader/ to ~/OpenTrader and run from there.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

echo "Tradenator 2.0 / OpenTrader — maintenance fixes"
echo ""

bash "${HERE}/fix-ollama.sh"
echo ""
bash "${HERE}/fix-research-cron.sh"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Verification"
echo "══════════════════════════════════════════════════"

export PATH="/usr/local/bin:${HOME}/.ollama/bin:${PATH}"
if command -v ollama >/dev/null 2>&1; then
  echo "  ✅ ollama in PATH: $(command -v ollama)"
  ollama list 2>/dev/null | head -5 | sed 's/^/      /' || true
else
  echo "  ⚠️  ollama still not in PATH — run: source ~/.bashrc"
fi

if curl -sf --max-time 3 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "  ✅ Ollama API :11434 reachable"
else
  echo "  ⚠️  Ollama API :11434 not reachable (ai_paper may use remote OLLAMA_HOST)"
fi

count="$(pgrep -cf "run_research_cycle.py" 2>/dev/null || echo 0)"
if [[ "$count" -le 1 ]]; then
  echo "  ✅ run_research_cycle instances: ${count}"
else
  echo "  ⚠️  run_research_cycle instances: ${count} (wait for extras to exit or re-run fix-research-cron.sh)"
fi

echo ""
echo "Done."
