@echo off
setlocal
cd /d "%~dp0\.."

echo [RF Workbench] Running command inside container: %*

where docker >nul 2>nul
if %errorlevel% equ 0 (
    docker compose exec rf-workbench %*
    if errorlevel 1 (
        echo [RF Workbench] Container not currently running in background. Running via ephemeral container...
        docker compose run --rm rf-workbench %*
    )
) else (
    rem Fallback to WSL docker if native docker is not in Windows PATH
    wsl -d Debian bash -c "cd /mnt/d/Workspace/rf/rf-workbench && (docker compose exec rf-workbench %* 2>/dev/null || docker compose run --rm rf-workbench %*)"
)
