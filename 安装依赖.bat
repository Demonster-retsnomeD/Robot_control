@echo off
chcp 65001 >nul
title 安装依赖
cd /d "%~dp0"
echo 安装 Flask 和相关库...
pip install flask flask-cors requests websocket-client
echo.
echo 安装完成！运行「启动.bat」开始使用
pause
