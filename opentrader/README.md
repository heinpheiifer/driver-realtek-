# OpenTrader

**One app** at **http://127.0.0.1:8010** — chart, Bookmap order flow, strategy, journal, backtest, and AI optimizer together.

- **Chart** — BTCUSD and other symbols via Yahoo / BlackBull / CSV
- **Bookmap Order Flow** — heatmap panel below the chart (replay or live Bookmap API)
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

If port 8010 is already in use:

```bash
FORCE=1 bash install_and_run.sh
```

Open **http://127.0.0.1:8010**

## Manual run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m opentrader
```

## Legacy alias

`opentrade.main:app` still works and points to the same unified app.
