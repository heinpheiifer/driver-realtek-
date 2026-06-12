# Open Trader OLD chart app + MT5 bridge

Your **original chart app** (Bookmap on the right, Heikin Ashi, drawing tools) runs on **http://127.0.0.1:8010**.

The **MT5 bridge** in this repo feeds **all BlackBull symbols** into that chart via a data API.

## Architecture

```
BlackBull MT5 (Windows)
        │
        ▼
scripts/mt5_python_bridge.py --all-symbols
        │  POST /api/market/blackbull/import
        ▼
MT5 bridge API (:8011 if chart on :8010)
        │
        ▼
Old Open Trader chart (:8010)
  GET /api/symbols
  GET /api/candles?symbol=XRPUSD&source=blackbull
  GET /api/bookmap/stream
```

## Step 1 — Start bridge API (Linux, where old chart runs)

```bash
cd ~/opentrader-app
git pull
bash install_and_run.sh          # creates .venv
bash scripts/start_mt5_bridge_api.sh
```

If your old chart is on **8010**, the bridge API auto-starts on **8011**.

## Step 2 — Run MT5 bridge (Windows, BlackBull MT5)

```cmd
cd opentrader-app
.venv\Scripts\pip install -r requirements-mt5.txt

set MT5_PATH=C:\Program Files\BlackBull Markets MT5\terminal64.exe
set MT5_LOGIN=YOUR_ACCOUNT
set MT5_PASSWORD=YOUR_PASSWORD
set MT5_SERVER=BlackBullMarkets-Live
set OPENTRADER_URL=http://YOUR-LINUX-IP:8011

.venv\Scripts\python scripts\mt5_python_bridge.py --all-symbols --interval 60
```

This pulls **every tradeable BlackBull symbol** (XRPUSD, BTCUSD, EURUSD, …) and pushes candles to Open Trader every 60 seconds.

## Step 3 — Point old chart app at bridge

In your old Open Trader app, set the BlackBull data URL to:

```
http://127.0.0.1:8011
```

(or your Linux machine IP from Windows)

## API endpoints (old app compatible)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/symbols` | All BlackBull symbols from last MT5 sync |
| `GET /api/candles?symbol=XRPUSD&timeframe=M1&source=blackbull` | OHLCV bars |
| `GET /api/bars?symbol=XRPUSD&timeframe=M1` | Alias for candles |
| `GET /api/bookmap/stream` | Order flow SSE |
| `POST /api/bookmap/event` | Bookmap Python API events |
| `POST /api/mt5/sync-all` | Force full symbol sync (Windows + MT5) |

## Same machine (Windows)

If old chart AND MT5 both run on Windows:

```cmd
set OPENTRADER_URL=http://127.0.0.1:8010
python scripts\mt5_python_bridge.py --all-symbols --interval 60
bash install_and_run.sh
```

## Files

| File | Role |
|------|------|
| `scripts/mt5_python_bridge.py` | **The MT5 bridge** — pulls all symbols |
| `trading/blackbull_mt5.py` | MT5 connector + symbol list + cache |
| `scripts/start_mt5_bridge_api.sh` | Start API on :8011 when chart uses :8010 |
| `trading_data/blackbull_symbols.json` | Cached symbol list from last sync |
