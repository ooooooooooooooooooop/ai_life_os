# AI Life OS (Real-World Avatar System)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English Documentation](README.md) | [中文文档](README_zh.md)

**AI Life OS** is an AI-driven personal operating system designed to treat the user as an "Executive Avatar" in the real world, with AI acting as the strategic planner. It helps manage time, habits, and goals through intelligent planning and retrospective analysis.

This repository contains **runnable code and documentation only** (no internal task plans or archives).

## ✨ Key Features

- **🧠 Auditable Planner**
  - Generates daily action plans based on current state, time, and energy levels.
  - Every AI decision comes with a logged rationale (Decision Reason).

- **📊 Habit Tracking & Analysis**
  - Automatically detects behavioral patterns from event logs.
  - Distinguishes between "Maintenance Rhythm" and "Exploration Tasks".

- **🔒 Privacy First**
  - **Local First**: Optimized for local Ollama models (Mistral, Qwen) to keep data private.
  - **Config Isolation**: Sensitive keys and personal data are strictly isolated.

- **🛡️ Robust Architecture**
  - **Event Sourcing**: System state is derived from an immutable event log.
  - **RIPER Principles**: Strict causal chain error handling.

## 📁 Repository Contents

- **core/** — Goal engine, event sourcing, LLM adapter, retrospective, rhythm detection.
- **config/** — Blueprint, model, prompts; use `config/model.example.yaml` → `config/local_model.yaml` for private keys.
- **web/** — Backend (FastAPI) and frontend (Vite/React) for dashboard and onboarding.
- **docs/** — Architecture and concept docs.
- **cli/, interface/, scheduler/, scripts/, tools/** — Entrypoints and utilities.

## 🚀 Quick Start

### 1. Prerequisites

Ensure Python 3.8+ is installed.

```bash
# Clone repository (replace with your repo URL if forking)
git clone https://github.com/yourusername/ai-life-os.git
cd ai-life-os

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate
# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Supports both OpenAI and local Ollama models.

1. Create local config:
   ```bash
   # Windows PowerShell
   copy config/model.example.yaml config/local_model.yaml
   ```

2. Edit `config/local_model.yaml`:
   ```yaml
   # Recommended: Local Ollama
   provider: ollama
   base_url: "http://localhost:11434"
   model_name: "mistral:latest"
   ```

### 3. Run

```bash
python main.py
```

On first run, the system enters **Cold Start Mode** to guide you through setting up your initial profile (City, Occupation, etc.).

## 📖 Usage Guide

- **Daily Check-in**: Run `main.py` to view today's plan and report progress.
- **Weekly Review**: Automatically triggers a retrospective analysis on Sundays (configurable).
- **Snapshots**: Data is safely persisted in the `data/` directory using event sourcing and snapshots.

## 🛠️ Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📜 License

This project is licensed under the [MIT License](LICENSE).
