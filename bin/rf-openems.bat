@echo off
setlocal
cd /d "%~dp0\.."

echo [RF Workbench] Launching AppCSXCAD (openEMS 3D Viewer)...
docker compose up -d
docker compose exec -d rf-workbench AppCSXCAD
start "" "http://localhost:6080/vnc.html"
