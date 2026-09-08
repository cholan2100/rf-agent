@echo off
setlocal
cd /d "%~dp0\.."

echo [RF AI Suite] Launching Autonomous Agentic RF PCB Designer...

where docker >nul 2>nul
if %errorlevel% equ 0 (
    docker compose exec -w /workspace/rf-workbench rf-workbench python3 -m agent.rf_agent_cli %*
    if errorlevel 1 (
        echo [RF AI Suite] Starting ephemeral container for agent...
        docker compose run --rm -w /workspace/rf-workbench rf-workbench python3 -m agent.rf_agent_cli %*
    )
) else (
    rem Fallback to WSL docker
    wsl -d Debian bash -c "cd /mnt/d/Workspace/rf/rf-workbench && docker compose exec -w /workspace/rf-workbench rf-workbench python3 -m agent.rf_agent_cli %*"
)

