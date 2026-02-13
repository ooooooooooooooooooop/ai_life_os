"""
Validate event log replay integrity.

Usage:
    python tools/validate_event_replay.py
    python tools/validate_event_replay.py --strict
"""
# ruff: noqa: E402
from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event_sourcing import (
    EVENT_LOG_PATH,
    apply_event,
    get_initial_state,
    validate_event_shape,
)  # noqa: E402


def validate_event_log(path: Path, strict: bool = False) -> int:
    if not path.exists():
        print(f"[validate] No event log found: {path}")
        return 0

    state = get_initial_state()
    total = 0
    parse_errors = 0
    shape_errors = 0
    apply_errors = 0
    schema_versions = Counter()
    event_types = Counter()

    with open(path, "r", encoding="utf-8") as f:
        for idx, raw_line in enumerate(f, start=1):
            if not raw_line.strip():
                continue
            total += 1

            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                parse_errors += 1
                print(f"[validate] line {idx}: invalid json ({exc})")
                continue

            schema_versions[str(event.get("schema_version", "legacy_or_missing"))] += 1
            event_types[str(event.get("type", "missing_type"))] += 1
            shape = validate_event_shape(event, strict=strict)
            if not shape["valid"]:
                shape_errors += 1
                missing = ", ".join(shape["missing"])
                print(f"[validate] line {idx}: missing required fields: {missing}")
                continue

            try:
                state = apply_event(state, event)
            except Exception as exc:  # pragma: no cover
                apply_errors += 1
                print(f"[validate] line {idx}: apply_event failed ({exc})")

    print(f"[validate] checked={total}")
    print(f"[validate] parse_errors={parse_errors}")
    print(f"[validate] shape_errors={shape_errors}")
    print(f"[validate] apply_errors={apply_errors}")
    print(f"[validate] schema_versions={dict(schema_versions)}")
    print(f"[validate] event_types={dict(event_types)}")

    if parse_errors or shape_errors or apply_errors:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI Life OS event replay integrity.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require canonical fields (type, timestamp, schema_version, event_id).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=EVENT_LOG_PATH,
        help="Override event log path.",
    )
    args = parser.parse_args()
    return validate_event_log(path=args.path, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
