# 参与 AI Life OS 贡献

感谢您有兴趣为 **AI Life OS** 做出贡献！我们欢迎任何形式的帮助。

## 🌟 如何通过贡献

### 1. 报告 Bug
- 提交 Issue 描述 Bug 的表现。
- 请务必包含复现步骤和错误日志 (`logs/error.log`)。

### 2. 功能建议
- 使用 **Discussion** 标签页或提交带有 `enhancement` 标签的 Issue。
- 提建议时，请遵循 RIPER 原则：先解释“为什么”（根本原因），再解释“怎么做”。

### 3.提交 Pull Request (PR)
1. **Fork** 本仓库。
2. 创建特性分支：`git checkout -b feature/amazing-feature`。
3. 提交您的修改。
4. **运行测试**：确保所有测试通过。
   ```bash
   python -m pytest
   ```
5. **代码检查**：
   ```bash
   ruff check .
   ```
6. 使用语义化 Commit 信息：`feat: add new planner logic`。
7. 推送分支并提交 PR。

## 🛠️ 开发环境搭建

1. **克隆与安装**：
   ```bash
   git clone https://github.com/yourusername/ai-life-os.git
   cd ai-life-os
   python -m venv .venv
   source .venv/bin/activate  # Windows 使用 .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **本地配置**：
   - 复制 `config/model.example.yaml` 为 `config/local_model.yaml`。
   - 配置您的本地 Ollama 或 OpenAI Key。

## 📐 代码规范
- **语言**: Python 3.8+。
- **风格**: 遵循 PEP 8，建议使用 `ruff` 进行格式化。
- **核心哲学**:
    - **拒绝 Magic Numbers**: 所有常量移至 `core/config_manager.py`。
    - **显式因果链**: 处理错误时，必须解释 *Why*（原因） -> *How*（对策）。
    - **隐私优先**: 严禁提交任何个人数据或密钥。

## 📜 许可证
参与贡献即表示您同意您的代码将在 MIT License 下授权。
