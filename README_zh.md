# AI Life OS（现实执行化身系统）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English Documentation](README.md) | [中文文档](README_zh.md)

AI Life OS 是一个由 AI 驱动的个人生活操作系统，帮助你通过计划与复盘管理时间、习惯和目标。

本仓库仅包含可运行代码与文档。

## 核心特性

- 可审计的计划生成（每个决策都有依据）
- 基于事件日志的习惯与节律分析
- 隐私优先（支持本地 Ollama）
- 基于事件溯源与快照的状态恢复

## 仓库结构

- `core/`：目标引擎、事件溯源、LLM 适配、复盘、节律逻辑
- `config/`：模型配置、提示词、蓝图与系统规则
- `web/`：FastAPI 后端与 Vite/React 前端
- `docs/`：架构与概念文档
- `cli/`、`interface/`、`scheduler/`、`scripts/`、`tools/`：入口与工具脚本

## 快速开始

### 1. 环境准备

安装 Python 3.8+。

```bash
python -m venv .venv
.\.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. 模型配置

```bash
copy config/model.example.yaml config/local_model.yaml
```

编辑 `config/local_model.yaml`：

```yaml
provider: ollama
base_url: "http://localhost:11434"
model_name: "mistral:latest"
```

### 3. 运行环境变量（可选）

复制 `.env.example` 为 `.env` 并按需修改。

关键变量：

- `AI_LIFE_OS_DATA_DIR`：运行数据目录（默认 `./data`）
- `AI_LIFE_OS_ALLOWED_ORIGINS`：CORS 来源列表（逗号分隔）
- `AI_LIFE_OS_HOST`：服务监听地址（默认 `0.0.0.0`）
- `AI_LIFE_OS_PORT`：服务端口（默认 `8010`）
- `AI_LIFE_OS_RELOAD`：是否开启热重载（开发可设 `1`，默认 `0`）
- `AI_LIFE_OS_DISABLE_WATCHERS`：禁用后台 watcher（测试推荐）

### 4. 启动

```bash
python main.py
```

## 数据迁移

将运行数据从 `./data` 迁移到自定义目录：

```bash
python tools/migrate_data_dir.py --dest D:\ai-life-os-data
```

迁移完成后设置：

```bash
AI_LIFE_OS_DATA_DIR=D:\ai-life-os-data
```

## 使用说明

- 日常使用：运行 `main.py`，通过 Dashboard/API 执行与反馈
- 周期复盘：由调度规则触发回顾分析
- 快照与日志：写入 `AI_LIFE_OS_DATA_DIR`（未设置时为 `data/`）

## 贡献

见 `CONTRIBUTING.md`。

## 许可证

MIT，见 `LICENSE`。
