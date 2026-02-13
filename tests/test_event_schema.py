import json

from core.event_sourcing import EVENT_SCHEMA_VERSION, validate_event_shape
from tools.migrate_event_log_schema import migrate, normalize_event_log


def test_validate_event_shape_strict_requires_schema_fields():
    legacy = {"type": "x", "timestamp": "2026-02-10T00:00:00"}
    loose = validate_event_shape(legacy, strict=False)
    strict = validate_event_shape(legacy, strict=True)

    assert loose["valid"] is True
    assert strict["valid"] is False
    assert "schema_version" in strict["missing"]
    assert "event_id" in strict["missing"]


def test_normalize_event_log_adds_schema_fields(tmp_path):
    src = tmp_path / "event_log.jsonl"
    src.write_text(
        json.dumps({"type": "goal_created", "timestamp": "2026-02-10T00:00:00"}) + "\n",
        encoding="utf-8",
    )

    events, report = normalize_event_log(src)
    assert report["total"] == 1
    assert report["changed"] == 1
    assert report["parse_errors"] == 0
    assert events[0]["schema_version"] == EVENT_SCHEMA_VERSION
    assert events[0]["event_id"].startswith("evt_")


def test_migrate_in_place_creates_backup_and_writes_normalized(tmp_path):
    src = tmp_path / "event_log.jsonl"
    src.write_text(
        json.dumps({"type": "task_created", "timestamp": "2026-02-10T00:00:00"}) + "\n",
        encoding="utf-8",
    )

    code = migrate(src=src, dest=None, apply=True, backup=True)
    assert code == 0

    backups = list(tmp_path.glob("event_log.backup_*.jsonl"))
    assert backups

    saved = json.loads(src.read_text(encoding="utf-8").strip())
    assert saved["schema_version"] == EVENT_SCHEMA_VERSION
    assert saved["event_id"].startswith("evt_")
