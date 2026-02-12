# Runtime Config Guide

This document summarizes runtime configuration used by AI Life OS.

## Environment Variables

### Server

- `AI_LIFE_OS_HOST`  
  Backend bind host. Default: `0.0.0.0`.

- `AI_LIFE_OS_PORT`  
  Backend port. Default: `8010`.

- `AI_LIFE_OS_RELOAD`  
  Enable auto-reload for development.  
  `1/true/yes` to enable, otherwise disabled by default.

### Data

- `AI_LIFE_OS_DATA_DIR`  
  Runtime data directory used for:
  - event log
  - state snapshot
  - goal registry
  - audit log
  - anchor files

  Default: `./data`

### API / CORS

- `AI_LIFE_OS_ALLOWED_ORIGINS`  
  Comma-separated CORS origins, for example:  
  `http://localhost:5173,http://127.0.0.1:5173`

  If set to `*`, credentials are disabled automatically.

### Watchers

- `AI_LIFE_OS_DISABLE_WATCHERS`  
  Disable background watcher threads (recommended for tests/CI).

## Runtime YAML Override

`config/runtime.yaml` can override fields from `core/config_manager.py`.

Examples:

```yaml
DAILY_TASK_LIMIT: 6
WEEKLY_REVIEW_DAY: 5
MIN_TASK_DURATION: 30
```

## Recommended Setups

### Local Development

```env
AI_LIFE_OS_RELOAD=1
AI_LIFE_OS_ALLOWED_ORIGINS=http://localhost:5173
```

### Test / CI

```env
AI_LIFE_OS_DISABLE_WATCHERS=1
AI_LIFE_OS_RELOAD=0
```

### Isolated Data Directory

```env
AI_LIFE_OS_DATA_DIR=D:\ai-life-os-data
```

Migrate existing data:

```bash
python tools/migrate_data_dir.py --dest D:\ai-life-os-data
```

## Event Log Schema Utilities

- Validate replay integrity:

```bash
python tools/validate_event_replay.py
python tools/validate_event_replay.py --strict
```

- Migrate event log to canonical schema fields (`schema_version`, `event_id`):

```bash
python tools/migrate_event_log_schema.py
python tools/migrate_event_log_schema.py --apply
```

## Guardian Autotune Operation

### Modes

- `shadow`  
  Generate proposals only, no lifecycle apply actions.

- `assist`  
  Keep proposal generation and enable lifecycle governance APIs
  (`review/apply/reject/rollback`) with manual operator control.

### Config API

- `GET /api/v1/guardian/autotune/config`
- `PUT /api/v1/guardian/autotune/config`

Main fields:

- `enabled`
- `mode` (`shadow | assist`)
- `llm_enabled`
- `trigger.lookback_days`
- `trigger.min_event_count`
- `trigger.cooldown_hours`
- `guardrails.max_int_step`
- `guardrails.max_float_step`
- `guardrails.min_confidence`
- `auto_evaluate.enabled`
- `auto_evaluate.horizon_hours`
- `auto_evaluate.lookback_days`
- `auto_evaluate.max_targets_per_cycle`

### Lifecycle API

- `GET /api/v1/guardian/autotune/lifecycle/latest`
- `GET /api/v1/guardian/autotune/lifecycle/history?days=14&limit=20`
- `GET /api/v1/guardian/autotune/evaluation/logs?days=14&limit=20`
- `POST /api/v1/guardian/autotune/lifecycle/review`
- `POST /api/v1/guardian/autotune/lifecycle/apply`
- `POST /api/v1/guardian/autotune/lifecycle/reject`
- `POST /api/v1/guardian/autotune/lifecycle/evaluate`
- `POST /api/v1/guardian/autotune/lifecycle/rollback`

Lifecycle request body supports:

- `proposal_id`
- `fingerprint`
- `actor`
- `source`
- `reason`
- `note`
- `force` (optional, default `false`; allows early/manual re-evaluation)

`lifecycle/history` returns:

- proposal lifecycle history chain (`proposed/reviewed/applied/rejected/evaluated/rolled_back`)
- operational metrics:
  - `autotune_review_turnaround_hours`
  - `autotune_apply_success_rate` (48h window)
  - `autotune_rollback_rate`
  - `post_apply_trust_delta_48h` (nullable with status/reason)

`evaluation/logs` returns cycle auto-evaluation run summaries:

- `status`, `mode`, `reason`
- `evaluated_count`, `target_count`, `error_count`
- `targets`, `errors`, `config`
- each `errors` item includes `proposal_id`, `fingerprint`, `status_code`, `detail`

### Operational Notes

- Lifecycle actions require `mode=assist`; otherwise API returns `409`.
- Apply records before/after threshold snapshots and supports one-step rollback.
- Apply events now record `trust_index_before` for post-apply trust tracking.
- `evaluate` action settles 48h outcome (`trust_index_after_48h`, trust delta, apply outcome status).
- `POST /api/v1/sys/cycle` now runs auto-evaluate for overdue apply records and returns
  `guardian_autotune_evaluation` payload (status, evaluated_count, targets, errors).
- Auto-evaluate scan/window/throughput are driven by `guardian_autotune.auto_evaluate` config.
- Each cycle auto-evaluation run is appended to event log and can be queried via
  `GET /api/v1/guardian/autotune/evaluation/logs`.
- Failed log items can be retried by calling
  `POST /api/v1/guardian/autotune/lifecycle/evaluate` with `force=true`.
- Lifecycle snapshot includes `rollback_recommendation` based on:
  - guardian safe mode active
  - low trust index
  - negative weekly alignment delta
