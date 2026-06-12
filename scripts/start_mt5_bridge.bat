@echo off
REM BlackBull MT5 bridge — run on Windows with BlackBull MT5 open
cd /d "%~dp0.."

if not exist .venv\Scripts\python.exe (
  echo Creating venv...
  python -m venv .venv
  .venv\Scripts\pip install -q -r requirements.txt -r requirements-mt5.txt
)

if not exist .env (
  echo.
  echo ERROR: Create .env from .env.blackbull.example first!
  echo   MT5_LOGIN=your_account
  echo   MT5_PASSWORD=your_password
  echo   MT5_SERVER=BlackBullMarkets-Live
  echo   MT5_PATH=C:\Program Files\BlackBull Markets MT5\terminal64.exe
  echo   OPENTRADER_URL=http://YOUR-LINUX-IP:8011
  echo.
  copy .env.blackbull.example .env
  notepad .env
  pause
  exit /b 1
)

echo Starting MT5 bridge — all BlackBull symbols to Open Trader...
echo Make sure BlackBull MT5 is running and logged in.
echo.
.venv\Scripts\python scripts\mt5_python_bridge.py --all-symbols --interval 60
pause
