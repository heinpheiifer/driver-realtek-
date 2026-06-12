# OpenTrader

Unified trading app combining:

- **Live Dashboard** — real-time paper PnL and open positions
- **Trade Journal** — every trade logged with full stats
- **Strategy Editor** — swarm agent settings (OpenTrade engine)
- **Backtest** — walk-forward validation
- **AI Optimizer** — runs until 65%+ win rate

OpenTrade is the research/backtest engine built into OpenTrader.

## Quick start

From repo root:

```bash
bash install_and_run.sh
```

Open **http://127.0.0.1:8080**

Port 8010:

```bash
PORT=8010 bash install_and_run.sh
```

## Manual run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m opentrader
```

## Legacy alias

`opentrade.main:app` still works and points to the same unified app.
