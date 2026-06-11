# OpenTrade

Web app for strategy editing, paper/live backtesting, and autonomous AI optimization.

## Run

```bash
pip install -r requirements.txt
python3 -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
uvicorn opentrade.main:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080`.

## Features

- Strategy library with editable swarm parameters
- Paper mode backtesting with walk-forward validation
- Live mode scaffold (MT5 EA export path via optimizer artifacts)
- AI optimizer loop targeting:
  - 65%+ win rate
  - 2-4 trades/day
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
uvicorn opentrade.main:app --host 0.0.0.0 --port 8080
```

Then start optimizer from the UI or CLI.
