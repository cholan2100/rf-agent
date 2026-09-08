param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AgentArgs
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "[RF AI Suite] Launching Autonomous Agentic RF PCB Designer..." -ForegroundColor Cyan

$running = docker compose ps --status running -q rf-workbench 2>$null
if ($running) {
    docker compose exec -w /workspace/rf-workbench rf-workbench python3 -m agent.rf_agent_cli @AgentArgs
} else {
    # Check if WSL docker is available
    $wslDocker = wsl -d Debian bash -c "docker compose ps --status running -q rf-workbench 2>/dev/null"
    if ($wslDocker) {
        wsl -d Debian bash -c "cd /mnt/d/Workspace/rf/rf-workbench && docker compose exec -w /workspace/rf-workbench rf-workbench python3 -m agent.rf_agent_cli $($AgentArgs -join \" \")"
    } else {
        Write-Host "[RF AI Suite] Starting ephemeral container..." -ForegroundColor Cyan
        wsl -d Debian bash -c "cd /mnt/d/Workspace/rf/rf-workbench && docker compose run --rm -w /workspace/rf-workbench rf-workbench python3 -m agent.rf_agent_cli $($AgentArgs -join \" \")"
    }
}

