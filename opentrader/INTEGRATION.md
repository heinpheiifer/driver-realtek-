# OpenTrader + OpenTrade Integration

Your screenshot shows **two separate pieces**:

| Component | Port | What it is |
|-----------|------|------------|
| **Open Trader chart UI** | `8010` | Your existing app (BTCUSD, Bookmap panel, BlackBull/Yahoo) |
| **OpenTrade research engine** | `8011` | Backtest, optimizer, journal, strategy API (this repo) |

Port 8010 was already in use because your chart app is running there.  
Do **not** stop it — run the research engine on **8011** instead.

## Setup

```bash
cd ~/opentrader-app
git pull
bash install_and_run.sh   # now defaults to 8011 if 8010 is taken
```

Or explicitly:

```bash
PORT=8011 bash install_and_run.sh
```

## Connect your Open Trader UI (8010) to the engine (8011)

Your Bookmap panel says: *"Enable the OpenTrader export addon in Bookmap (Python API)"*

### Option A — Bookmap Python API → our bridge

Point Bookmap export to POST events:

```
POST http://127.0.0.1:8011/api/bookmap/event
Content-Type: application/json

{
  "type": "large_print",
  "price": 62939.77,
  "size": 1.5,
  "delta": 0.8,
  "side": "buy"
}
```

Status check:

```
GET http://127.0.0.1:8011/api/bookmap/status
```

Live SSE stream (for your Order Flow panel):

```
GET http://127.0.0.1:8011/api/bookmap/stream
```

### Option B — Replay mode (no Bookmap license needed)

Starts synthetic order-flow signals from CSV:

```
POST http://127.0.0.1:8011/api/bookmap/start-replay
{"csv_path": "trading_data/eurusd_m1.csv", "tick_ms": 200}
```

### Option C — Wire your frontend JavaScript

In your Open Trader chart app (8010), fetch from 8011:

```javascript
const API = "http://127.0.0.1:8011";

// Order flow heatmap
const flow = await fetch(`${API}/api/orderflow?window=120`).then(r => r.json());

// Bookmap live stream
const es = new EventSource(`${API}/api/bookmap/stream`);
es.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.cvd !== undefined) updateCVD(data.cvd);
  if (data.signals) paintSignals(data.signals);
};

// Backtest / optimizer
await fetch(`${API}/api/backtest`, { method: "POST", ... });
await fetch(`${API}/api/optimizer/start`, { method: "POST", ... });
```

CORS is enabled for `http://127.0.0.1:8010` and `http://localhost:8010`.

## API summary (engine on 8011)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Engine status |
| `GET /api/orderflow` | Bookmap-style heatmap data |
| `GET /api/bookmap/stream` | Live CVD + signals SSE |
| `POST /api/bookmap/event` | Ingest Bookmap Python API events |
| `POST /api/bookmap/start-replay` | Demo replay without Bookmap |
| `POST /api/backtest` | Run strategy backtest |
| `POST /api/optimizer/start` | AI optimizer (65%+ win rate gate) |
| `GET /api/journal` | Trade journal + stats |
| `POST /api/session/start` | Paper trading session |

## Full UI (optional)

Our built-in dashboard (strategy editor, journal tabs) is at:

```
http://127.0.0.1:8011/
```

Your chart app stays on **8010**; research engine on **8011**.
