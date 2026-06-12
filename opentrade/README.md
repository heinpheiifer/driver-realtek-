# OpenTrade

Web app for strategy editing, paper/live backtesting, and autonomous AI optimization.

## Run

**First time setup** (creates `.venv` and installs dependencies):

```bash
bash scripts/setup_opentrade.sh
```

**Start OpenTrade:**

```bash
bash scripts/run_opentrade.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn opentrader.main:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010` (or set `PORT=8080` for a different port).

If you see `No module named uvicorn`, you skipped `pip install -r requirements.txt` — run setup first.

## Features

- Strategy library with editable swarm parameters
- Paper mode backtesting with walk-forward validation
- Live mode scaffold (MT5 EA export path via optimizer artifacts)
- AI optimizer loop targeting:
  - 65%+ win rate
  - drawdown and return gates
- Equity curve + trade table in UI

## API

- `GET /api/strategies`
- `POST /api/strategies`
- `POST /api/backtest`
- `POST /api/optimizer/start`
- `GET /api/optimizer/jobs/{job_id}`

## tmux long-running optimizer

```bash
tmux new -s opentrade -c /workspace
uvicorn opentrader.main:app --host 127.0.0.1 --port 8010
```

Then start optimizer from the UI or CLI.
