@echo off
setlocal
cd /d "%~dp0\.."

echo [RF Workbench] Launching Qucs-S...
docker compose up -d
docker compose exec -d rf-workbench qucs-s
start "" "http://localhost:6080/vnc.html"
