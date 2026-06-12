# Open Trader — Unified App

Everything runs in **one app** on **http://127.0.0.1:8010**:

| Feature | Location |
|---------|----------|
| Price chart (BTCUSD, etc.) | Main panel |
| Bookmap order flow (below chart) | Heatmap / Signals / Volume tabs |
| Strategy settings | Right panel → Settings |
| Trade journal + stats | Right panel → Journal |
| Backtest results | Right panel → Backtest |
| AI optimizer (65%+ win rate) | Right panel → Optimizer |
| Paper trading session | Left sidebar → Start Session |

## Quick start

```bash
cd ~/opentrader-app
git pull
bash install_and_run.sh
```

Open **http://127.0.0.1:8010**

If port 8010 is busy (old separate app still running):

```bash
FORCE=1 bash install_and_run.sh
```

## Market data sources

Use the toolbar to pick symbol and data source:

- **Yahoo** — live BTCUSD, EURUSD, etc. via Yahoo Finance
- **BlackBull** — uses cached CSV (wire MT5/BlackBull API in `trading/market_data.py`)
- **CSV** — local file in `trading_data/`

## Bookmap integration

The order flow panel below the chart accepts:

1. **Replay mode** (default) — synthetic signals from loaded OHLCV
2. **Bookmap Python API** — POST events to the same server:

```
POST http://127.0.0.1:8010/api/bookmap/event
Content-Type: application/json

{"type": "large_print", "price": 62939.77, "size": 1.5, "delta": 0.8, "side": "buy"}
```

Live SSE stream: `GET http://127.0.0.1:8010/api/bookmap/stream`

## API (all on :8010)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/market/candles?symbol=BTCUSD&source=yahoo` | Load chart + orderflow data |
| `GET /api/bookmap/stream` | Live CVD + signals SSE |
| `POST /api/bookmap/event` | Ingest Bookmap Python API events |
| `POST /api/backtest` | Run strategy backtest |
| `POST /api/optimizer/start` | AI optimizer (65%+ win rate gate) |
| `GET /api/journal` | Trade journal + stats |
| `POST /api/session/start` | Paper trading session |

No second port required.
