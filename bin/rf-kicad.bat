@echo off
setlocal
cd /d "%~dp0\.."

echo [RF Workbench] Launching KiCad...
docker compose up -d
docker compose exec -d rf-workbench kicad
start "" "http://localhost:6080/vnc.html"
