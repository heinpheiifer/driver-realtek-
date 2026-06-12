# Recover your old chart — files missing from opentrade-app

Your `/api/health` shows:

```json
"serving": "missing_old_ui",
"old_app_index": null,
"chart_discovered": null
```

**Your original chart HTML is not on disk** in `/home/heinz/opentrade-app` (and backups don't have it either). The server is correctly **not** showing the new git app — but there's nothing to load.

## Step 1 — search your whole home folder

```bash
cd ~/opentrader-app
git pull
bash scripts/recover_old_chart.sh
```

Look for lines marked **★** — those are likely your old chart.

## Step 2 — point the server at it

If you find a path, edit `/home/heinz/opentrade-app/.env`:

```
OPENTRADER_USE_OLD_UI=1
OPENTRADER_OLD_APP=/home/heinz/opentrade-app
OPENTRADER_UI_INDEX=/full/path/to/your/chart.html
MT5_AUTO_SYNC=0
```

Then:

```bash
cd /home/heinz/opentrade-app
bash scripts/stop_opentrader.sh
FORCE=1 bash run.sh
```

## Step 3 — verify

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

Need `"serving": "old_app"` and `"old_app_index"` set.

## If search finds nothing

The old app may have lived in a **different folder** before integrate. Please check:

- `~/opentrader-app` (git clone — not the same as opentrade-app)
- `~/Desktop`, `~/Documents`, Downloads zip files
- Another PC or backup drive
- Trash: `~/.local/share/Trash/files/`

**Question:** Before all this, which command did you use to start the old chart?  
(e.g. `python server.py`, `npm start`, from which folder?)

That folder is where your real UI files are.
