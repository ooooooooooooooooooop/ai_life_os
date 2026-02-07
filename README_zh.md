# AI Life OS (真实化身助手)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English Documentation](README.md) | [中文文档](README_zh.md)

**AI Life OS** 是一个 AI 驱动的个人生活操作系统，旨在通过智能规划、习惯追踪和自我复盘，帮助你将自己视为现实世界的“执行化身 (Avatar)”，而由 AI 辅助进行“决策规划”。

本仓库仅包含**可运行代码与文档**（不含内部任务计划或归档）。

## ✨ 核心特性

- **🧠 智能规划器 (Auditable Planner)**
  - 基于当前状态、时间和精力生成每日行动计划。
  - 所有决策均有据可查（Decision Reason）。

- **📊 习惯识别与追踪**
  - 自动从事件日志中分析行为模式。
  - 区分“维持性习惯”与“探索性任务”。

- **🔒 隐私优先设计**
  - **Local First**: 完美支持 Ollama 本地模型（如 Mistral, Qwen），数据不出本地。
  - **配置隔离**: 敏感 Key 与个人数据严格隔离。

- **🛡️ 健壮的系统架构**
  - **Event Sourcing**: 基于不可变事件日志的事实来源。
  - **RIPER 原则**: 严格的因果链错误处理机制。

## 📁 仓库内容

- **core/** — 目标引擎、事件溯源、LLM 适配、复盘、节奏检测等核心逻辑。
- **config/** — 蓝图、模型与提示词配置；敏感配置请使用 `config/model.example.yaml` 复制为 `config/local_model.yaml`。
- **web/** — 后端 (FastAPI) 与前端 (Vite/React)，提供看板与引导。
- **docs/** — 架构与概念说明。
- **cli/, interface/, scheduler/, scripts/, tools/** — 入口与工具脚本。

## 🚀 快速开始

### 1. 环境准备

确保已安装 Python 3.8+。

```bash
# 克隆项目（若 fork 请替换为你的仓库地址）
git clone https://github.com/yourusername/ai-life-os.git
cd ai-life-os

# 创建虚拟环境
python -m venv .venv

# 激活环境 (Windows)
.\.venv\Scripts\activate
# 激活环境 (Linux/Mac)
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置系统

本项目不仅支持 OpenAI，还深度优化了本地 Ollama 支持。

1. 复制示例配置：
   ```bash
   # Windows PowerShell
   copy config/model.example.yaml config/local_model.yaml
   ```

2. 编辑 `config/local_model.yaml`：
   ```yaml
   # 推荐：使用本地 Ollama (需先安装 Ollama 并 pull 模型)
   provider: ollama
   base_url: "http://localhost:11434"
   model_name: "mistral:latest"
   ```

### 3. 运行

```bash
python main.py
```

首次运行时，系统会进入**冷启动模式**，引导您输入基础信息（城市、职业等）以建立初始状态。

## 📖 使用指南

- **日常打卡**: 运行 `main.py` 查看今日计划并反馈执行结果。
- **周报复盘**: 每周日（默认，可配置）自动触发周报分析。
- **状态快照**: 系统会自动管理状态快照，数据保存在 `data/` 目录下。

## 🛠️ 参与贡献

欢迎提交 Issue 或 Pull Request！详情请查阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📜 许可证

本项目采用 [MIT License](LICENSE) 开源。
