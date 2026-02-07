# ============================================================
# AI Life OS - 一键启动脚本
# ============================================================
# 功能: 自动检测环境并启动后端服务（含前端静态资源）
# 使用: 双击运行或在 PowerShell 中执行 .\start.ps1
# ============================================================

param(
    [switch]$Dev,      # 开发模式（启用热重载）
    [int]$Port = 8010  # 服务端口，默认 8010
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- 打印 Banner ---
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║         🌟 AI Life OS v1.0 🌟             ║" -ForegroundColor Cyan
Write-Host "  ║       Personal Life Operating System      ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# --- 1. 检测 Python 环境 ---
Write-Host "[1/3] 检测 Python 环境..." -ForegroundColor Yellow

# 优先级: conda cla 环境 > 本地 .venv > 全局 python
$pythonCmd = $null

# 检查 conda cla 环境
$condaInfo = conda info --envs 2>$null | Select-String "cla"
if ($condaInfo) {
    Write-Host "  ✅ 发现 Conda 环境: cla" -ForegroundColor Green
    # 激活 conda 环境
    conda activate cla 2>$null
    $pythonCmd = "python"
}
else {
    # 检查本地 .venv
    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Host "  ✅ 发现本地虚拟环境: .venv" -ForegroundColor Green
        $pythonCmd = $venvPython
    }
    else {
        Write-Host "  ⚠️  未发现虚拟环境，使用系统 Python" -ForegroundColor Yellow
        $pythonCmd = "python"
    }
}

# 验证 Python 可用
try {
    $pyVersion = & $pythonCmd --version 2>&1
    Write-Host "  ✅ Python 版本: $pyVersion" -ForegroundColor Green
}
catch {
    Write-Host "  ❌ Python 未安装或不可用！" -ForegroundColor Red
    Write-Host "  请安装 Python 3.8+ 后重试" -ForegroundColor Red
    pause
    exit 1
}

# --- 2. 检查依赖 ---
Write-Host "[2/3] 检查依赖..." -ForegroundColor Yellow

$checkResult = & $pythonCmd -c "import fastapi, uvicorn, httpx, yaml, pydantic" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠️  缺少依赖，正在安装..." -ForegroundColor Yellow
    & $pythonCmd -m pip install -r "$root\requirements.txt" -q
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ 依赖安装完成" -ForegroundColor Green
    }
    else {
        Write-Host "  ❌ 依赖安装失败，请手动运行: pip install -r requirements.txt" -ForegroundColor Red
        pause
        exit 1
    }
}
else {
    Write-Host "  ✅ 依赖已就绪" -ForegroundColor Green
}

# --- 3. 启动服务 ---
Write-Host "[3/3] 启动服务..." -ForegroundColor Yellow

$reloadFlag = if ($Dev) { "--reload" } else { "" }

Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║            🚀 服务启动成功 🚀              ║" -ForegroundColor Green
Write-Host "  ╠═══════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "  ║  🌐 访问地址: http://localhost:$Port       ║" -ForegroundColor Green
Write-Host "  ║  📖 API 文档: http://localhost:$Port/docs  ║" -ForegroundColor Green
Write-Host "  ║  ⏹️  停止服务: 按 Ctrl+C                  ║" -ForegroundColor Green
Write-Host "  ╚═══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# 设置环境变量
$env:PYTHONPATH = "$root;$env:PYTHONPATH"

# 启动 uvicorn
if ($Dev) {
    & $pythonCmd -m uvicorn web.backend.app:app --host 0.0.0.0 --port $Port --reload
}
else {
    & $pythonCmd -m uvicorn web.backend.app:app --host 0.0.0.0 --port $Port
}
