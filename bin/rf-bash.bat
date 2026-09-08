@echo off
setlocal
cd /d "%~dp0\.."

echo ======================================================================
echo   Opening Interactive Bash Terminal in RF Workbench
echo ======================================================================

where docker >nul 2>nul
if %errorlevel% equ 0 (
    docker compose exec -it rf-workbench bash
    if errorlevel 1 (
        echo [RF Workbench] Container not currently running. Starting interactive shell...
        docker compose run --rm -it rf-workbench bash
    )
) else (
    rem Fallback to WSL docker if native docker is not in Windows PATH
    wsl -d kali-linux bash -c "cd /mnt/d/Workspace/rf/rf-workbench && (docker compose exec -it rf-workbench bash 2>/dev/null || docker compose run --rm -it rf-workbench bash)"
)
