# Windows PowerShell — start MT5 bridge for Linux/macOS clients
# Run on the PC where MetaTrader 5 is installed.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$venv = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    . $venv
}

Write-Host "==> Installing bridge dependencies (if needed)..."
pip install -q -r bridge\requirements.txt

$port = if ($env:MT5_BRIDGE_PORT) { $env:MT5_BRIDGE_PORT } else { "8021" }
Write-Host "==> Starting MT5 bridge on port $port"
Write-Host "    Linux .env: MT5_BRIDGE_URL=http://YOUR_WINDOWS_IP:$port"
Write-Host "    Optional:    MT5_BRIDGE_TOKEN=your-secret-token"
Write-Host ""
Write-Host "Keep MetaTrader 5 open on this machine while the bridge runs."

python bridge\server.py --host 0.0.0.0 --port $port
