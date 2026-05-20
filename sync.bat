@echo off
cd /d %~dp0
echo Auto-sync started. Keep this window open while developing.
echo Changes will be pushed to GitHub automatically.
echo.
python auto_sync.py
pause
