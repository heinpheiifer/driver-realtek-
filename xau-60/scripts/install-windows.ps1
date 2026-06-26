# XAU-60 / MT5 Trading Bot — Windows install (MT5 live trading)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> XAU-60 MT5 Trading Bot — install (Windows)" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtual environment..."
    python -m venv .venv
}

Write-Host "==> Installing Python packages (includes MetaTrader5)..."
& .\.venv\Scripts\pip.exe install -U pip wheel
& .\.venv\Scripts\pip.exe install -r requirements.txt

New-Item -ItemType Directory -Force -Path logs, data | Out-Null

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host ""
    Write-Host "Edit .env with your MT5 credentials:" -ForegroundColor Yellow
    Write-Host "  MT5_LOGIN, MT5_PASSWORD, MT5_SERVER"
    Write-Host "  MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe"
    Write-Host ""
}

Write-Host "==> Install complete." -ForegroundColor Green
Write-Host ""
Write-Host "Before trading:"
Write-Host "  1. Open MetaTrader 5 and log into a DEMO account"
Write-Host "  2. Tools -> Options -> Expert Advisors -> Allow algorithmic trading"
Write-Host "  3. Edit .env with login/password/server"
Write-Host ""
Write-Host "Start dashboard:  .\scripts\start-windows.ps1"
Write-Host "Test config:      .\.venv\Scripts\python.exe main.py --dry-run"
Write-Host "CLI live bot:     .\.venv\Scripts\python.exe main.py"
Write-Host ""
