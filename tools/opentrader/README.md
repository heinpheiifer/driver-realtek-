# OpenTrader / Tradenator 2.0 maintenance scripts

Fixes for common issues on **heinz-Predator** (`~/OpenTrader`).

## Fixes

| Script | What it does |
|--------|----------------|
| `fix-ollama.sh` | Inst/finds Ollama, adds to `~/.bashrc`, writes `~/OpenTrader/.env.ollama`, starts `ollama serve`, verifies API |
| `fix-research-cron.sh` | Adds `flock` to `run_research_cron.sh`, dedupes crontab, stops extra `run_research_cycle.py` PIDs |
| `fix-all.sh` | Runs both + verification |

## Run on your laptop

```bash
# Option A — from this repo after pull
cd ~/tradenator-xau60   # or path where driver-realtek- was cloned
git pull
bash tools/opentrader/fix-all.sh

# Option B — copy to OpenTrader
cp -r tools/opentrader ~/OpenTrader/scripts/maintenance
bash ~/OpenTrader/scripts/maintenance/fix-all.sh
```

## After running

```bash
source ~/.bashrc
ollama list
curl -s http://127.0.0.1:11434/api/tags | head
pgrep -af "run_research_cycle"
```

## Optional: use wrapper for AI paper

If you restart AI paper via watchdog/cron, point it at:

```bash
~/OpenTrader/scripts/run_ai_paper.sh
```

(created by `fix-ollama.sh` — sources `.env.ollama` before starting Python)
