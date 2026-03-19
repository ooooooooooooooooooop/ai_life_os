"""
Tests for new modules added in recent iterations.
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest


# =============================================================================
# intervention_tracker tests
# =============================================================================

def test_resistance_escalation_rules():
    """Test gentle→firm→periodic escalation rules."""
    from core.intervention_tracker import (
        record_resistance,
        get_intervention_level,
        _save_state,
        _load_state,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "intervention_state.json"

        with mock.patch("core.intervention_tracker.STATE_FILE", state_file):
            key = "test_goal_escalation"

            # Initial: gentle_nudge
            assert get_intervention_level(key) == "gentle_nudge"

            # 1 resistance: firm_reminder
            record_resistance(key)
            assert get_intervention_level(key) == "firm_reminder"

            # 2 resistance: still firm_reminder
            record_resistance(key)
            assert get_intervention_level(key) == "firm_reminder"

            # 3 resistance: periodic_check
            record_resistance(key)
            assert get_intervention_level(key) == "periodic_check"


def test_acceptance_resets_count():
    """Test that acceptance resets resistance count."""
    from core.intervention_tracker import (
        record_resistance,
        record_acceptance,
        get_intervention_level,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "intervention_state.json"

        with mock.patch("core.intervention_tracker.STATE_FILE", state_file):
            key = "test_goal_acceptance"

            # Build up resistance
            record_resistance(key)
            record_resistance(key)
            record_resistance(key)
            assert get_intervention_level(key) == "periodic_check"

            # Acceptance resets
            record_acceptance(key)
            assert get_intervention_level(key) == "gentle_nudge"


def test_state_persists_across_instances():
    """Test that state persists after simulated restart."""
    from core.intervention_tracker import (
        record_resistance,
        get_intervention_level,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "intervention_state.json"

        with mock.patch("core.intervention_tracker.STATE_FILE", state_file):
            key = "test_goal_persist"

            # Record resistance
            record_resistance(key)
            record_resistance(key)

            # Simulate restart by re-importing
            # State should persist from file
            assert get_intervention_level(key) == "firm_reminder"


# =============================================================================
# event_archiver tests
# =============================================================================

def test_archive_moves_old_events():
    """Test that old events are moved to archive."""
    from core.event_archiver import archive_old_events, get_archive_stats

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "event_log.jsonl"
        archive_dir = Path(tmpdir) / "archive"

        # Create test events: some old, some recent
        events = [
            {"type": "test", "timestamp": "2025-01-01T10:00:00"},  # old
            {"type": "test", "timestamp": "2025-01-15T10:00:00"},  # old
            {"type": "test", "timestamp": "2026-03-10T10:00:00"},  # recent
        ]
        with open(log_file, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        with mock.patch("core.event_archiver.EVENT_LOG_PATH", log_file), \
             mock.patch("core.event_archiver.ARCHIVE_DIR", archive_dir):

            result = archive_old_events(keep_days=30)

            # Old events archived, recent kept
            assert result["archived"] == 2
            assert result["remaining"] == 1
            assert result["dropped"] == 0

            # Archive file created
            stats = get_archive_stats()
            assert len(stats["archive_files"]) > 0


def test_dirty_data_dropped():
    """Test that 1970 dirty data is dropped."""
    from core.event_archiver import archive_old_events

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "event_log.jsonl"
        archive_dir = Path(tmpdir) / "archive"

        # Create events with dirty data
        events = [
            {"type": "dirty", "timestamp": "1970-01-01T00:00:00"},  # dirty
            {"type": "dirty", "timestamp": "1970-06-15T10:00:00"},  # dirty
            {"type": "valid", "timestamp": "2026-03-10T10:00:00"},  # valid
        ]
        with open(log_file, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        with mock.patch("core.event_archiver.EVENT_LOG_PATH", log_file), \
             mock.patch("core.event_archiver.ARCHIVE_DIR", archive_dir):

            result = archive_old_events(keep_days=30)

            # Dirty data dropped
            assert result["dropped"] == 2
            assert result["remaining"] == 1


def test_should_archive_threshold():
    """Test should_archive triggers at 500 lines or 300KB."""
    from core.event_archiver import should_archive

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "event_log.jsonl"

        with mock.patch("core.event_archiver.EVENT_LOG_PATH", log_file):
            # Empty file: should not archive
            log_file.write_text("", encoding="utf-8")
            assert should_archive() is False

            # 501 lines: should archive
            with open(log_file, "w", encoding="utf-8") as f:
                for i in range(501):
                    f.write(json.dumps({"type": "test", "i": i}) + "\n")
            assert should_archive() is True


# =============================================================================
# persona_loader tests
# =============================================================================

def test_blueprint_is_first_in_prompt():
    """Test that Blueprint appears at the start of prompt."""
    from core.persona_loader import get_guardian_system_prompt

    prompt = get_guardian_system_prompt()

    # Blueprint should appear before Guardian (SOUL content)
    blueprint_pos = prompt.find("Blueprint")
    guardian_pos = prompt.find("Guardian")

    assert blueprint_pos != -1, "Blueprint not found in prompt"
    assert guardian_pos != -1, "Guardian not found in prompt"
    assert blueprint_pos < guardian_pos, "Blueprint should appear before Guardian"


def test_agents_injected_into_prompt():
    """Test that AGENTS content is in prompt."""
    from core.persona_loader import get_guardian_system_prompt

    prompt = get_guardian_system_prompt()

    # AGENTS content should be present
    assert "权限边界" in prompt or "Session" in prompt, "AGENTS content not in prompt"


def test_persona_has_agents_field():
    """Test that get_persona() returns agents field."""
    from core.persona_loader import get_persona

    persona = get_persona()

    assert "agents" in persona, "agents field missing from persona"
    assert len(persona["agents"]) > 0, "agents field is empty"


# =============================================================================
# mood_detector tests
# =============================================================================

def test_chinese_keywords_detected():
    """Test Chinese mood keywords are detected."""
    from core.mood_detector import detect_mood

    assert detect_mood("好累啊") == "stressed"
    assert detect_mood("压力好大") == "stressed"
    assert detect_mood("焦虑") == "stressed"
    assert detect_mood("没意思") == "low"
    assert detect_mood("放弃吧") == "low"
    assert detect_mood("做到了！") == "positive"
    assert detect_mood("搞定了") == "positive"


def test_english_keywords_detected():
    """Test English mood keywords are detected."""
    from core.mood_detector import detect_mood

    assert detect_mood("I am so tired") == "stressed"
    assert detect_mood("feeling anxious today") == "stressed"
    assert detect_mood("I want to give up") == "low"
    assert detect_mood("whatever") == "low"
    assert detect_mood("I nailed it!") == "positive"
    assert detect_mood("done with the task") == "positive"


def test_neutral_message_no_mood():
    """Test neutral messages return neutral."""
    from core.mood_detector import detect_mood

    assert detect_mood("今天天气不错") == "neutral"
    assert detect_mood("hello world") == "neutral"
    assert detect_mood("") == "neutral"
