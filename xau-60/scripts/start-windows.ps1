# Start XAU-60 dashboard on port 8020 (Windows; 8010 = Tradenator)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "Run .\scripts\install-windows.ps1 first" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}

New-Item -ItemType Directory -Force -Path logs | Out-Null

$env:STREAMLIT_SERVER_PORT = "8020"
$env:STREAMLIT_SERVER_ADDRESS = "0.0.0.0"

Write-Host "Starting XAU-60 on http://localhost:8020" -ForegroundColor Green
& .\.venv\Scripts\streamlit.exe run ui/app.py `
    --server.port=8020 `
    --server.address=0.0.0.0 `
    --browser.gatherUsageStats=false
