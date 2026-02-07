@echo off
cd /d "%~dp0"
title AI Life OS Server
echo ==========================================
echo Starting AI Life OS (Port 8010)
echo ==========================================

:: 尝试激活 conda 环境 (如果可用)
call conda activate cla 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Could not activate 'cla' environment automatically.
    echo Please ensure you are running this in an environment with dependencies installed.
)

python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server crashed or failed to start.
    echo Please make sure dependencies are installed: pip install -r requirements.txt
    pause
)
