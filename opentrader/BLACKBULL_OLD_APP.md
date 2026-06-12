# BlackBull / XRPUSD data for old OpenTrader chart

Your chart UI is in `~/OpenTrader`. **BlackBull data** came from the OpenTrader **Django backend** or **MT5 bridge** — not the chart HTML alone.

## Option A — Start Django backend (if OpenTrader has manage.py)

```bash
cd ~/opentrader-app
git pull
bash scripts/integrate_old_app.sh /home/heinz/opentrade-app

bash scripts/start_opentrader_django.sh /home/heinz/OpenTrader
```

Add to `/home/heinz/opentrade-app/.env`:

```
OPENTRADER_BACKEND_URL=http://127.0.0.1:8000
```

Restart chart:

```bash
cd /home/heinz/opentrade-app
bash scripts/stop_opentrader.sh
FORCE=1 bash run.sh
```

Market API (`/api/candles?symbol=XRPUSD`) is proxied to Django → MT5.

## Option B — MT5 bridge (Windows PC with BlackBull MT5)

On **Windows** (MT5 open + logged in):

```cmd
set OPENTRADER_URL=http://YOUR-LINUX-IP:8010
set MT5_LOGIN=your_account
set MT5_PASSWORD=your_password
set MT5_SERVER=BlackBullMarkets-Live
python scripts\mt5_python_bridge.py --all-symbols --interval 60
```

## Option C — One command (tries Django, then bridge)

```bash
cd ~/opentrader-app
git pull
FORCE=1 bash scripts/start_opentrader_stack.sh
```

## Test XRPUSD

```bash
curl -s "http://127.0.0.1:8010/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull" | head -c 400
curl -s "http://127.0.0.1:8010/api/mt5/status/" | python3 -m json.tool
```

Should return JSON with `"bars": [...]`, not 404.

## Check status

```bash
curl -s http://127.0.0.1:8010/api/health | python3 -m json.tool
```

Look for `"django_backend": "http://127.0.0.1:8000"` when Django is running.

Django log: `tail -f /home/heinz/OpenTrader/.opentrader_django.log`  
Bridge log: `tail -f /home/heinz/opentrade-app/.mt5_bridge.log`
