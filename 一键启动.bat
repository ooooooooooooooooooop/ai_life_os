@echo off
chcp 65001 >nul
title AI Life OS
cd /d "%~dp0"

echo.
echo ==========================================
echo          AI Life OS - 一键启动
echo ==========================================
echo.

:: 尝试激活 conda cla 环境
call conda activate cla 2>nul

:: 检查依赖
python -c "import fastapi, uvicorn" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] 正在安装依赖...
    pip install -r requirements.txt -q
)

echo [INFO] 正在启动服务...
echo.
echo ==========================================
echo   访问地址: http://localhost:8010
echo   API 文档: http://localhost:8010/docs
echo   停止服务: 按 Ctrl+C
echo ==========================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 服务启动失败！
    echo 请确认已安装依赖: pip install -r requirements.txt
    pause
)
