# Project Change Record (Brief)

Last updated: 2026-02-09

## Scope

This record summarizes recent issue-first stabilization work before feature iteration.

## Change Batches

1. Runtime hardening
- `main.py`: runtime host/port/reload now controlled by env vars.
- `web/backend/app.py`: CORS origins configurable; credentials only enabled for explicit origins.
- `web/backend/routers/onboarding.py`: removed `timestamp: None` writes.
- `web/backend/routers/api.py`: `/api/v1/state` compatibility mapping for mixed state shapes.

2. Test baseline repair
- Disabled watcher side effects in tests (`core/rule_evaluator.py`, `tests/conftest.py`).
- Removed blocking SSE behavior from default API test path.
- Updated legacy tests to current behavior/model.

3. Data path isolation
- Added centralized path module: `core/paths.py`.
- Introduced `AI_LIFE_OS_DATA_DIR` support across core persistence modules.
- Updated scripts/tools to use centralized data directory.

4. Encoding and docs cleanup
- Rewrote corrupted docs/files to clean UTF-8:
  - `README.md`
  - `README_zh.md`
  - `.env.example`
  - `CONTRIBUTING.md`
- Replaced mojibake-heavy core modules with clean equivalents:
  - `core/config_manager.py`
  - `core/blueprint_anchor.py`
  - `core/snapshot_manager.py`

5. Operations and CI
- Added runtime operations guide: `docs/operations/runtime-config.md`.
- Added data migration tool: `tools/migrate_data_dir.py`.
- Added CI workflow: `.github/workflows/ci.yml` (ruff + pytest).

## Validation

- Full test run: `51 passed, 5 skipped`.
- API key endpoint check: `/api/v1/state` returns 200 with expected fields.

## Current Status

- Stabilization phase completed.
- Project is ready to switch to feature-iteration mode.

## Planning/Archive Workflow

Current approach is valid:
- Keep active records under `.taskflow/active/`.
- Keep one-step incremental logs in task `progress.md`.
- Archive by phase/task completion into `.taskflow/archive/`.

This lightweight summary file should remain as the high-level index, while detailed execution stays in `.taskflow`.
