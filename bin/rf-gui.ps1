$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Starting RF Workbench Container with Web Desktop" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

docker compose up -d

Write-Host "Waiting for noVNC web server to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "Launching web desktop in browser..." -ForegroundColor Green
Start-Process "http://localhost:6080/vnc.html"

Write-Host ""
Write-Host "Web Desktop is active at http://localhost:6080/vnc.html" -ForegroundColor Cyan
Write-Host "Default Password: rfworkbench" -ForegroundColor Yellow
