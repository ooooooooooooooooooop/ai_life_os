"""
Migrate event log records to canonical schema fields.

Default mode is dry-run.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event_sourcing import EVENT_LOG_PATH, EVENT_SCHEMA_VERSION, normalize_event  # noqa: E402


def normalize_event_log(src: Path) -> Tuple[List[dict], Dict[str, object]]:
    """
    Read and normalize all valid event records from src.
    """
    normalized_events: List[dict] = []
    schema_before = Counter()
    schema_after = Counter()
    report: Dict[str, object] = {
        "total": 0,
        "changed": 0,
        "parse_errors": 0,
        "schema_before": schema_before,
        "schema_after": schema_after,
    }

    with open(src, "r", encoding="utf-8") as f:
        for idx, raw_line in enumerate(f, start=1):
            if not raw_line.strip():
                continue
            report["total"] += 1
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                report["parse_errors"] += 1
                print(f"[parse-error] line={idx}")
                continue

            schema_before[str(event.get("schema_version", "legacy_or_missing"))] += 1
            normalized = normalize_event(event)
            schema_after[str(normalized.get("schema_version"))] += 1
            if normalized != event:
                report["changed"] += 1
            normalized_events.append(normalized)

    return normalized_events, report


def _backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}.backup_{stamp}{path.suffix}")


def _write_event_log(path: Path, events: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def migrate(
    src: Path,
    dest: Path | None = None,
    apply: bool = False,
    backup: bool = True,
) -> int:
    if not src.exists():
        print(f"[skip] source event log not found: {src}")
        return 0

    normalized_events, report = normalize_event_log(src)

    print("=== Event Schema Migration Report ===")
    print(f"source: {src}")
    print(f"target schema_version: {EVENT_SCHEMA_VERSION}")
    print(f"total records: {report['total']}")
    print(f"changed records: {report['changed']}")
    print(f"parse errors: {report['parse_errors']}")
    print(f"schema before: {dict(report['schema_before'])}")
    print(f"schema after: {dict(report['schema_after'])}")

    if not apply:
        print("\n[dry-run] no files changed")
        return 0

    if report["parse_errors"] > 0:
        print("[abort] parse errors detected; fix raw file before apply")
        return 1

    target = dest.resolve() if dest else src.resolve()
    if target == src.resolve() and backup and src.exists():
        backup_file = _backup_path(src)
        shutil.copy2(src, backup_file)
        print(f"[backup] {backup_file}")

    _write_event_log(target, normalized_events)
    print(f"[done] migrated event log: {target}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate event log to canonical schema.")
    parser.add_argument(
        "--src",
        type=Path,
        default=EVENT_LOG_PATH,
        help="source event log path",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="destination event log path (default: overwrite source when --apply)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply migration changes (default is dry-run)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="when applying in-place, do not create backup file",
    )
    args = parser.parse_args()

    raise SystemExit(
        migrate(
            src=args.src,
            dest=args.dest,
            apply=args.apply,
            backup=not args.no_backup,
        )
    )


if __name__ == "__main__":
    main()
