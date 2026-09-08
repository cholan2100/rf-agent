$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Opening Interactive Bash Terminal in RF Workbench" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$running = docker compose ps --status running -q rf-workbench 2>$null
if ($running) {
    docker compose exec -it rf-workbench bash
} else {
    Write-Host "[RF Workbench] Starting interactive shell in container..." -ForegroundColor Cyan
    docker compose run --rm -it rf-workbench bash
}
