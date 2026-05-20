@echo off
chcp 65001 >nul
title Reeman Robot Control Server
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║   Reeman Moon Knight 2.0 控制系统         ║
echo  ║   正在启动...                              ║
echo  ╚═══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 安装依赖
echo [1/2] 检查依赖包...
pip install -r requirements.txt -q --disable-pip-version-check

:: 启动服务器
echo [2/2] 启动控制服务器...
echo.
echo  访问地址: http://localhost:5000
echo  按 Ctrl+C 停止服务器
echo.
start "" http://localhost:5000
python server.py

pause
