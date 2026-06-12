# BlackBull MT5 → Open Trader Chart

Open Trader loads **real BlackBull market data** from your MT5 terminal — the same prices you trade on.

## Option A — Python bridge (recommended, Windows)

Run on the same PC as your BlackBull MT5 terminal:

```bash
pip install MetaTrader5 requests

set MT5_PATH=C:\Program Files\BlackBull Markets MT5\terminal64.exe
set MT5_LOGIN=YOUR_ACCOUNT
set MT5_PASSWORD=YOUR_PASSWORD
set MT5_SERVER=BlackBullMarkets-Live
set OPENTRADER_URL=http://127.0.0.1:8010

python scripts/mt5_python_bridge.py --symbol BTCUSD --timeframe M5 --interval 15
```

This syncs live MT5 candles to Open Trader every 15 seconds.

## Option B — Direct MT5 connection (same machine)

Set environment variables before starting Open Trader:

```bash
export MT5_PATH="/path/to/terminal64.exe"
export MT5_LOGIN=12345678
export MT5_PASSWORD=your_password
export MT5_SERVER=BlackBullMarkets-Live

bash install_and_run.sh
```

In the app, select **BlackBull** and click **Sync MT5** or **Load**.

## Option C — MT5 script export (any OS)

1. Copy `scripts/BlackBullExportToOpenTrader.mq5` into your MT5 `Scripts` folder
2. Run the script on your chart in BlackBull MT5
3. Copy exported CSV from `MQL5/Files/blackbull_import/` to Open Trader:

   ```
   trading_data/blackbull_import/btcusd_m5.csv
   ```

4. Click **Load** with **BlackBull** selected

## Option D — HTTP import from custom EA

POST candles from any MT5 Expert Advisor:

```
POST http://127.0.0.1:8010/api/market/blackbull/import
Content-Type: application/json

{
  "symbol": "BTCUSD",
  "timeframe": "M5",
  "candles": [
    {"timestamp": "2026-06-11 12:00:00", "open": 63200, "high": 63250, "low": 63180, "close": 63220, "volume": 120}
  ]
}
```

## API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/market/mt5/status` | MT5 connection status |
| `POST /api/market/mt5/connect` | Try connecting to MT5 |
| `POST /api/market/blackbull/sync` | Pull latest candles from MT5 |
| `POST /api/market/blackbull/import` | Push candles from MT5 EA/bridge |
| `GET /api/market/candles?source=blackbull` | Load chart data |

## BlackBull server names

Common MT5 server values:
- `BlackBullMarkets-Live`
- `BlackBullMarkets-Demo`

Check **Tools → Options → Server** in your MT5 terminal for the exact name.

## Linux note

MetaTrader5 Python API requires the MT5 terminal on **Windows**. On Linux, use Option C (CSV export) or run the Python bridge on a Windows machine/VPS with MT5 installed.
