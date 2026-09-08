param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

if (-not $CommandArgs) {
    Write-Host "Usage: rf-run <command> [args...]" -ForegroundColor Yellow
    Write-Host "Example: rf-run python examples/simple_led/run_pipeline.py" -ForegroundColor Cyan
    exit 1
}

$running = docker compose ps --status running -q rf-workbench 2>$null
if ($running) {
    docker compose exec rf-workbench @CommandArgs
} else {
    Write-Host "[RF Workbench] Starting ephemeral container to run command..." -ForegroundColor Cyan
    docker compose run --rm rf-workbench @CommandArgs
}
