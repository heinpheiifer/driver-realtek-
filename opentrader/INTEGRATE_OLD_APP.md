# Bring back YOUR old Open Trader chart app

## One command

```bash
cd ~/opentrader-app
git pull
bash scripts/integrate_old_app.sh /home/heinz/opentrade-app
bash scripts/stop_opentrader.sh
FORCE=1 bash scripts/bring_back_old_app.sh
```

## Find your chart if restore fails

```bash
bash scripts/find_old_chart.sh /home/heinz/opentrade-app
```

If it finds your chart path, add to `/home/heinz/opentrade-app/.env`:

```
OPENTRADER_USE_OLD_UI=1
OPENTRADER_UI_INDEX=/full/path/to/your/chart.html
```

Then:

```bash
cd /home/heinz/opentrade-app
FORCE=1 bash run.sh
```

## Verify (must NOT say "builtin")

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

- `"serving": "old_app"` — your chart
- `"serving": "missing_old_ui"` — old mode on but chart file not found (won't show new app)
- `"serving": "builtin"` — new git app (wrong for you)

## New git app instead?

```
OPENTRADER_USE_NEW_UI=1
```
