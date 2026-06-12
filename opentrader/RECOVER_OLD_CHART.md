# Your old chart is in ~/OpenTrader (not opentrade-app)

Recovery found:

```
/home/heinz/OpenTrader/frontend/index.html
/home/heinz/OpenTrader/frontend/dist/index.html
/home/heinz/OpenTrader/staticfiles/index.html
```

`opentrade-app` is only the **engine** folder — your real chart was never there.

## One command

```bash
cd ~/opentrader-app
git pull
FORCE=1 bash scripts/connect_opentrader_chart.sh
```

This points the engine at `~/OpenTrader/frontend/dist/index.html` and starts on port **8010**.

## Verify

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

Expect:

```json
"serving": "old_app",
"old_app": "/home/heinz/OpenTrader",
"old_app_index": "/home/heinz/OpenTrader/frontend/dist/index.html"
```
