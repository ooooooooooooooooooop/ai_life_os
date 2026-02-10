# Contributing to AI Life OS

Thanks for contributing to AI Life OS.

## How to Contribute

### 1. Report Bugs

- Open an issue with clear reproduction steps.
- Include relevant logs and stack traces.
- Describe expected behavior vs actual behavior.

### 2. Propose Features

- Open an issue with the `enhancement` label.
- Explain the problem first, then the proposed solution.
- Keep scope explicit: in-scope and out-of-scope.

### 3. Submit Pull Requests

1. Fork and create a branch:
   - `git checkout -b feature/your-change`
2. Implement and test your change.
3. Run local checks:
   - `ruff check .`
   - `PYTHONPATH=. AI_LIFE_OS_DISABLE_WATCHERS=1 pytest -q`
4. Use clear commit messages.
5. Open a PR with:
   - problem statement
   - change summary
   - test evidence

## Local Development Setup

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate
pip install -r requirements.txt
pip install ruff pytest
```

### Optional Runtime Config

Copy `.env.example` to `.env` and set values as needed.

Common variables:

- `AI_LIFE_OS_DATA_DIR`: runtime data directory (default `./data`)
- `AI_LIFE_OS_ALLOWED_ORIGINS`: CORS origins list
- `AI_LIFE_OS_HOST`: backend host
- `AI_LIFE_OS_PORT`: backend port
- `AI_LIFE_OS_RELOAD`: hot reload for local dev
- `AI_LIFE_OS_DISABLE_WATCHERS`: disable background watchers (recommended in tests)

## Coding Guidelines

- Python 3.8+.
- Keep configuration in explicit config files/modules.
- Avoid hard-coded secrets and personal data.
- Prefer small, testable, behavior-preserving changes.

## License

By contributing, you agree your contributions are licensed under MIT.
