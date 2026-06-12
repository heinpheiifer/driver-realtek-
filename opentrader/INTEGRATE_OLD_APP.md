# Add new features to YOUR old Open Trader app (one server, port 8010)

Your old app at **`/home/heinz/opentrade-app`** already has chart + MT5.  
This merges the **engine only** (backtest, journal, optimizer) — **your UI is never overwritten**.

## One command (recommended)

From the git repo on your machine:

```bash
cd ~/opentrader-app
git pull
FORCE=1 bash scripts/setup_old_app.sh /home/heinz/opentrade-app
```

This will:
1. Backup your chart UI
2. Merge the engine (skips `opentrader/static/` so git UI cannot replace yours)
3. Restore UI from backup if `index.html` is missing
4. Install deps and start on port **8010**

## Manual steps

```bash
cd ~/opentrader-app
git pull
bash scripts/integrate_old_app.sh /home/heinz/opentrade-app
cd /home/heinz/opentrade-app
FORCE=1 bash run.sh
```

## UI missing / wrong chart?

Restore from automatic backup:

```bash
cd /home/heinz/opentrade-app
bash scripts/restore_old_ui.sh
FORCE=1 bash run.sh
```

Backups live in `.opentrader_ui_backup/latest/`.

If your chart `index.html` is in an unusual path, set in `.env`:

```
OPENTRADER_UI_INDEX=/home/heinz/opentrade-app/path/to/index.html
```

## Verify

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

You want:
- `"serving": "old_app"`
- `"old_app_index": "/home/heinz/opentrade-app/..."` (your file, not git engine UI)

## .env

```
OPENTRADER_OLD_APP=/home/heinz/opentrade-app
MT5_AUTO_SYNC=0
MT5_PATH="C:\Program Files\BlackBull Markets MT5\terminal64.exe"
```

MT5 stays as in your old app — no duplicate sync.
