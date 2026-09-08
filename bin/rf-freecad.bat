@echo off
setlocal
cd /d "%~dp0\.."

echo [RF Workbench] Launching FreeCAD...
docker compose up -d
docker compose exec -d rf-workbench freecad
start "" "http://localhost:6080/vnc.html"
