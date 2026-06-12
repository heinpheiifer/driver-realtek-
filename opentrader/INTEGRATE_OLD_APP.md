# Use YOUR old Open Trader app UI + git engine API (one server, port 8010)

Your old app at **`/home/heinz/opentrade-app`** keeps its chart, Bookmap panel, drawing tools, etc.  
The git repo adds the **engine** (MT5 auto-sync, backtest, journal, optimizer) under the same port.

## One-time setup

```bash
cd ~/opentrader-app          # git clone (engine source)
git pull

bash scripts/integrate_old_app.sh /home/heinz/opentrade-app
```

This copies `trading/`, `opentrade/`, `opentrader/`, scripts, and requirements into your old app folder.

## Run (replaces separate old server + bridge)

```bash
cd /home/heinz/opentrade-app
bash run.sh
```

Open **http://127.0.0.1:8010** — your **old UI**, with **all new APIs** on the same origin.

## What you get (old UI + new engine)

| Feature | Endpoint |
|---------|----------|
| BlackBull chart data (auto) | `GET /api/candles?source=blackbull` |
| All symbols | `GET /api/symbols` |
| Bookmap order flow | `GET /api/bookmap/stream` |
| Backtest | `POST /api/backtest` |
| Optimizer | `POST /api/optimizer/start` |
| Journal | `GET /api/journal` |
| MT5 auto-sync on startup | `MT5_AUTO_SYNC=1` in `.env` |

## .env (Windows + MT5 on same PC)

Edit `/home/heinz/opentrade-app/.env`:

```
OPENTRADER_OLD_APP=/home/heinz/opentrade-app
MT5_LOGIN=your_account
MT5_PASSWORD=your_password
MT5_SERVER=BlackBullMarkets-Live
MT5_PATH=C:\Program Files\BlackBull Markets MT5\terminal64.exe
MT5_AUTO_SYNC=1
```

## Why two folders before?

- **Old app** = your chart frontend (not in GitHub)
- **Git repo** = engine we built separately

`integrate_old_app.sh` merges them so you run **one app**, like before.

## Linux + MT5 on Windows

Set in `.env` on Linux — bridge still pushes from Windows if needed:

```
OPENTRADER_URL=http://LINUX-IP:8010
```

Or run `scripts/start_mt5_bridge.bat` on Windows pointing at your Linux IP.
