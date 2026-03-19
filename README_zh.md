# AI Life OS（现实执行化身系统）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English Documentation](README.md) | [中文文档](README_zh.md)

AI Life OS 是一个由 AI 驱动的个人生活操作系统，帮助你通过计划与复盘管理时间、习惯和目标。

**当前版本**: v3.0 Eudaimonia Guardian Edition

## 核心特性

- **Guardian 复盘引擎**: 5种偏差信号检测，完整证据链支持
- **本能劫持检测**: 任务放弃、重复推迟等行为检测
- **Safe Mode**: 完整的安全模式用户体验
- **Authority 系统**: 三级干预级别（温和提醒/坚定提醒/周期检查）
- **可审计的计划生成**: 每个决策都有依据，可追溯到事件
- **基于事件日志的习惯与节律分析**: 事件溯源架构
- **隐私优先**: 支持本地 Ollama，数据完全本地化
- **双层架构**: L1 Substrate（生存基质）+ L2 Flourishing（蓬勃生长）
- **Blueprint 锚定决策**: 核心价值观注入 Guardian system prompt，作为最高优先级
- **AGENTS 工作手册**: Guardian 权限边界与干预节奏规范，实时参与每次决策
- **情绪感知**: 中英文情绪关键词检测，自动写入事件日志
- **干预抵抗持久化**: 抵抗计数跨重启保存，三级升级规则（温和→坚定→周期）
- **事件日志归档**: 自动清理超龄日志，脏数据丢弃，主文件保持轻量
- **前端实时推送**: SSE 连接监听 Guardian 事件，无需刷新自动更新界面
- **多模型路由**: 按任务类型自动选择模型（guardian/strategic/fast/embedding）

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
