# Add new features to YOUR old Open Trader app (one server, port 8010)

Your old app at **`/home/heinz/opentrade-app`** already has:

- Chart UI (Heikin Ashi, drawing tools, Bookmap panel)
- **BlackBull MT5** — already connected and pulling data

The git repo only adds the **extra engine** on the same port: backtest, journal, optimizer, Bookmap API.

**You do not need a second app, a separate MT5 bridge, or duplicate autosync.**

## One-time setup

```bash
cd ~/opentrader-app          # git clone (engine source)
git pull

bash scripts/integrate_old_app.sh /home/heinz/opentrade-app
```

This merges `trading/`, `opentrade/`, `opentrader/`, and scripts into your old app folder.  
Existing files in your old app are **kept** (no wipe).

## Run

Stop your old server if it is still on 8010, then:

```bash
cd /home/heinz/opentrade-app
bash run.sh
```

If port 8010 is busy:

```bash
cd /home/heinz/opentrade-app
FORCE=1 bash run.sh
```

Open **http://127.0.0.1:8010** — same UI, same MT5, plus new APIs.

## What gets added (old UI + MT5 unchanged)

| Feature | Endpoint |
|---------|----------|
| Backtest | `POST /api/backtest` |
| Optimizer | `POST /api/optimizer/start` |
| Journal | `GET /api/journal` |
| Bookmap order flow | `GET /api/bookmap/stream` |
| Chart data (same as before) | `GET /api/candles?source=blackbull` |

## MT5 — already handled by your old app

Integration sets **`MT5_AUTO_SYNC=0`** so the git engine does **not** start a second MT5 sync thread.

Your existing `.env` MT5 settings (`MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, `MT5_PATH`) stay as they are.

Only set `MT5_AUTO_SYNC=1` if you want the git engine to *also* run background sync (usually not needed).

## .env (typical)

```
OPENTRADER_OLD_APP=/home/heinz/opentrade-app
MT5_AUTO_SYNC=0
MT5_LOGIN=...
MT5_PASSWORD=...
MT5_SERVER=BlackBullMarkets-Live
MT5_PATH="C:\Program Files\BlackBull Markets MT5\terminal64.exe"
```

If `run.sh` fails with `FilesBlackBull: command not found`, quote `MT5_PATH` in `.env` (spaces in the path).  
Or pull latest and re-run `integrate_old_app.sh` — `run.sh` no longer sources `.env` in bash.

## Verify

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

Look for `"serving": "old_app"` and `"mt5_autosync": {"enabled": false, ...}`.

## Why two folders before?

- **Old app** = your chart + MT5 (not in GitHub)
- **Git repo** = backtest / journal / optimizer we built separately

`integrate_old_app.sh` merges them into **one app**, like you asked.
