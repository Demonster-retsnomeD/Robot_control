@echo off
echo =============================================
echo   Robot Control - Build Windows EXE
echo =============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    pause & exit /b 1
)

echo [1/4] Installing PyInstaller + pywebview...
pip install pyinstaller pywebview -q
if errorlevel 1 ( echo [ERROR] Install failed & pause & exit /b 1 )

echo [2/4] Installing dependencies...
pip install -r requirements.txt -q

echo [3/4] Building EXE (1-3 min)...
pyinstaller --name RobotControl --distpath dist --workpath build_tmp --noconfirm --windowed --add-data "templates;templates" --add-data "static;static" --hidden-import flask --hidden-import flask_cors --hidden-import flask_login --hidden-import werkzeug --hidden-import werkzeug.security --hidden-import requests --hidden-import jinja2 --hidden-import markupsafe --hidden-import webview --hidden-import webview.platforms.winforms --collect-all webview launcher.py
if errorlevel 1 ( echo [ERROR] Build failed & pause & exit /b 1 )

echo [4/4] Copying config...
if not exist dist\RobotControl\config.json (
    copy config.json dist\RobotControl\config.json >nul
)

echo.
echo =============================================
echo   Done! EXE: dist\RobotControl\RobotControl.exe
echo.
echo   To create installer: install Inno Setup then
echo   right-click installer.iss and compile
echo =============================================
echo.
pause
