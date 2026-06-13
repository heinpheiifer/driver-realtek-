# Where is my old OpenTrader app?

Your **original working app** is NOT the git repo we've been patching. It lives here:

| What | Path |
|------|------|
| **Your chart + Django app** | `/home/heinz/OpenTrader` |
| **Git engine (new)** | `/home/heinz/opentrade-app` and `~/opentrader-app` |

The new git engine was layered on top and broke live BlackBull/MT5.  
Your old app had **Django + MT5 bridge → all BlackBull symbols**.

## Run YOUR old app (one command)

```bash
cd ~/opentrader-app && git pull
bash scripts/run_my_old_app.sh
```

**Chart URL (Firefox or any browser):** http://127.0.0.1:8010

Do **not** use port **8011** for the chart — that is the MT5 bridge API only (blank/broken UI).

The script finds `~/OpenTrader/manage.py`, creates a `.venv` there if needed, and installs Django automatically.

If Django install fails manually:

```bash
cd ~/OpenTrader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# if no requirements.txt:
pip install django djangorestframework django-cors-headers python-dotenv requests
python manage.py migrate
python manage.py runserver 127.0.0.1:8010
```

This:
1. Stops the new git engine on port 8010
2. Starts **your** OpenTrader from `~/OpenTrader` (Django if `manage.py` exists)
3. Patches the UI so **Bookmap Order Flow sits below the chart** (not on the right)
4. Prints the MT5 bridge command for live BlackBull data

## MT5 bridge (live BlackBull — same as before)

On **Windows** with BlackBull MT5 open:

```cmd
set OPENTRADER_URL=http://127.0.0.1:8010
set MT5_LOGIN=your_account
set MT5_PASSWORD=your_password
set MT5_SERVER=BlackBullMarkets-Live
python scripts\mt5_python_bridge.py --all-symbols --interval 60
```

On **Linux** with Wine MT5:

```bash
bash ~/opentrader-app/scripts/setup_live_blackbull.sh /home/heinz/opentrade-app
```

## Find your app if paths differ

```bash
bash ~/opentrader-app/scripts/recover_old_chart.sh
find ~/OpenTrader -name manage.py
find ~ -maxdepth 4 -name manage.py 2>/dev/null
```

## Do NOT use (these are the new broken path)

- `bash scripts/fix_opentrader_now.sh` — patches git engine, not your old app
- `bash scripts/integrate_old_app.sh` — overwrites your setup with git engine
- `FORCE=1 bash run.sh` in opentrade-app — starts **new** FastAPI, not your Django app

## If Django log shows errors

```bash
tail -50 /home/heinz/OpenTrader/.opentrader_django.log
cd /home/heinz/OpenTrader && python3 manage.py runserver 127.0.0.1:8010
```
