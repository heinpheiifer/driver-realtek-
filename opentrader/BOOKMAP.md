# Bookmap → Open Trader

Your chart shows **"Waiting for signals… Enable the OpenTrader export addon in Bookmap (Python API)"**.

Open Trader accepts Bookmap events on the **same server** as the chart:

```
POST http://127.0.0.1:8010/api/bookmap/event
```

Live stream (for the Order Flow panel):

```
GET http://127.0.0.1:8010/api/bookmap/stream
```

## Quick test (no Bookmap license needed)

Start Open Trader, then replay order-flow from your BlackBull CSV:

```bash
cd ~/opentrader-app
source .venv/bin/activate
python scripts/opentrader_bookmap_addon.py --replay trading_data/blackbull_import/xrpusd_h1.csv
```

Or use the built-in replay API:

```bash
curl -X POST http://127.0.0.1:8010/api/bookmap/start-replay \
  -H "Content-Type: application/json" \
  -d '{"csv_path":"trading_data/blackbull_import/xrpusd_h1.csv","tick_ms":150}'
```

## Wire your Bookmap Python addon

In your Bookmap export script, POST each event:

```python
import requests

OPENTRADER = "http://127.0.0.1:8010"

def on_bookmap_event(event_type, price, size, delta, side):
    requests.post(f"{OPENTRADER}/api/bookmap/event", json={
        "type": event_type,      # sweep | absorption | large_print | imbalance
        "price": price,
        "size": size,
        "delta": delta,
        "side": side,            # buy | sell
    }, timeout=2)
```

Or pipe JSON lines to our bridge:

```bash
python scripts/opentrader_bookmap_addon.py
# then paste: {"type":"large_print","price":1.105,"size":5000,"delta":120,"side":"buy"}
```

## Two Open Trader UIs?

| UI | How to tell |
|----|-------------|
| **Original chart app** (your screenshot) | Bookmap panel on the **right**, drawing tools, Heikin Ashi |
| **Unified app from git** | Bookmap **below** chart, strategy sidebar left, settings panel right |

Both can use the same API on `:8010`. If Bookmap stays idle, the frontend may not be subscribed to `/api/bookmap/stream` — try the replay test above to confirm the backend works.

## BlackBull + XRPUSD on Linux

Export from MT5 on Windows, import on Linux:

```bash
bash scripts/import_blackbull_csv.sh /path/to/xrpusd_h1.csv XRPUSD H1
```

Then **BlackBull → Load** in the chart.
