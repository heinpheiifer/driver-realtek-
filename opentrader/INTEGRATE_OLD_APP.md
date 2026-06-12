# Bring back YOUR old Open Trader chart app

## One command

```bash
cd ~/opentrader-app
git pull
FORCE=1 bash scripts/bring_back_old_app.sh
```

Open **http://127.0.0.1:8010** — your original chart (Heikin Ashi, Bookmap, drawing tools).

## What it does

1. Backs up UI files
2. Merges engine API (backtest, journal, optimizer) **without** overwriting your chart
3. Restores from `.opentrader_ui_backup/latest` if git UI replaced your chart
4. Sets `OPENTRADER_USE_OLD_UI=1` in `.env`
5. Starts on port 8010

## Manual restore only

```bash
cd /home/heinz/opentrade-app
bash scripts/restore_old_ui.sh
FORCE=1 bash run.sh
```

## Verify

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

Want `"serving": "old_app"` and `"old_app_index"` pointing at your chart `index.html`.

## New git UI instead?

Set in `.env`: `OPENTRADER_USE_NEW_UI=1`
