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

### Lifecycle API

- `GET /api/v1/guardian/autotune/lifecycle/latest`
- `POST /api/v1/guardian/autotune/lifecycle/review`
- `POST /api/v1/guardian/autotune/lifecycle/apply`
- `POST /api/v1/guardian/autotune/lifecycle/reject`
- `POST /api/v1/guardian/autotune/lifecycle/rollback`

Lifecycle request body supports:

- `proposal_id`
- `fingerprint`
- `actor`
- `source`
- `reason`
- `note`

### Operational Notes

- Lifecycle actions require `mode=assist`; otherwise API returns `409`.
- Apply records before/after threshold snapshots and supports one-step rollback.
- Lifecycle snapshot includes `rollback_recommendation` based on:
  - guardian safe mode active
  - low trust index
  - negative weekly alignment delta
