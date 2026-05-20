@echo off
cd /d %~dp0
echo Starting Robot Control server...
start "" "http://localhost:5000"
python server.py --dev
pause
