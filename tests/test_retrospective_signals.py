from datetime import datetime

import core.retrospective as retrospective


def _signal_by_name(signals, name):
    return next(s for s in signals if s["name"] == name)


def test_detect_deviation_signals_flags_skip_and_l2_interruptions():
    events = [
        {
            "event_id": "evt_1",
            "type": "task_updated",
            "timestamp": "2026-02-10T10:05:00",
            "payload": {"updates": {"status": "skipped"}},
        },
        {
            "event_id": "evt_2",
            "type": "task_updated",
            "timestamp": "2026-02-10T10:25:00",
            "payload": {"updates": {"status": "skipped"}},
        },
    ]

    signals = retrospective._detect_deviation_signals(events, days=7)

    repeated_skip = _signal_by_name(signals, "repeated_skip")
    l2_interruption = _signal_by_name(signals, "l2_interruption")
    stagnation = _signal_by_name(signals, "stagnation")

    assert repeated_skip["active"] is True
    assert repeated_skip["count"] == 2
    assert l2_interruption["active"] is True
    assert l2_interruption["count"] == 2
    assert stagnation["active"] is True


def test_detect_deviation_signals_clears_stagnation_when_progress_exists():
    events = [
        {
            "event_id": "evt_3",
            "type": "progress_updated",
            "timestamp": datetime.now().isoformat(),
            "payload": {"message": "made progress"},
        }
    ]

    signals = retrospective._detect_deviation_signals(events, days=7)
    repeated_skip = _signal_by_name(signals, "repeated_skip")
    l2_interruption = _signal_by_name(signals, "l2_interruption")
    stagnation = _signal_by_name(signals, "stagnation")

    assert repeated_skip["active"] is False
    assert l2_interruption["active"] is False
    assert stagnation["active"] is False


def test_generate_guardian_retrospective_includes_alignment_trend(monkeypatch):
    monkeypatch.setattr(retrospective, "load_events_for_period", lambda days: [])
    monkeypatch.setattr(
        retrospective,
        "_guardian_rhythm",
        lambda events, days: {"broken": False, "summary": "ok"},
    )
    monkeypatch.setattr(
        retrospective,
        "_guardian_alignment",
        lambda events: {"deviated": False, "summary": "ok"},
    )
    monkeypatch.setattr(
        retrospective,
        "_goal_alignment_trend",
        lambda events, days: {
            "available": True,
            "summary": "目标对齐趋势整体稳定。",
            "points": [{"date": "2026-02-11", "avg_score": 72.0, "samples": 2}],
            "active_anchor_version": "v1",
        },
    )
    monkeypatch.setattr(
        retrospective,
        "_guardian_friction",
        lambda events: {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
    )
    monkeypatch.setattr(
        retrospective,
        "_guardian_l2_protection",
        lambda events, days, thresholds=None: {
            "ratio": 0.8,
            "level": "high",
            "protected": 4,
            "interrupted": 1,
            "opportunities": 5,
            "summary": "good",
            "trend": [],
        },
    )
    monkeypatch.setattr(
        retrospective,
        "_detect_deviation_signals",
        lambda events, days, thresholds=None: [],
    )
    monkeypatch.setattr(
        retrospective,
        "_guardian_observations",
        lambda rhythm, alignment, friction, l2_protection, deviation_signals: ["ok"],
    )

    payload = retrospective.generate_guardian_retrospective(days=7)
    assert "trend" in payload["alignment"]
    assert payload["alignment"]["trend"]["available"] is True
    assert payload["alignment"]["trend"]["active_anchor_version"] == "v1"
    assert payload["l2_protection"]["ratio"] == 0.8


def test_guardian_l2_protection_ratio_uses_deep_work_l2_events(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "_build_l2_reference_maps",
        lambda: (
            {"g_l2": "L2_FLOURISHING", "g_l1": "L1_SUBSTRATE"},
            {"t1": "g_l2", "t2": "g_l2", "t3": "g_l1"},
        ),
    )
    events = [
        {
            "type": "task_updated",
            "timestamp": "2026-02-10T10:00:00",
            "payload": {"id": "t1", "updates": {"status": "completed"}},
        },
        {
            "type": "task_updated",
            "timestamp": "2026-02-10T10:20:00",
            "payload": {"id": "t2", "updates": {"status": "skipped"}},
        },
        {
            "type": "task_updated",
            "timestamp": "2026-02-10T15:20:00",
            "payload": {"id": "t3", "updates": {"status": "completed"}},
        },
    ]

    payload = retrospective._guardian_l2_protection(events, days=7)
    assert payload["protected"] == 1
    assert payload["interrupted"] == 1
    assert payload["opportunities"] == 2
    assert payload["ratio"] == 0.5


def test_detect_deviation_signals_respects_configurable_thresholds(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 3,
            "l2_interruption": 2,
            "stagnation_days": 5,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.50,
        },
    )
    events = [
        {
            "event_id": "evt_11",
            "type": "task_updated",
            "timestamp": "2026-02-10T10:05:00",
            "payload": {"updates": {"status": "skipped"}},
        },
        {
            "event_id": "evt_12",
            "type": "task_updated",
            "timestamp": "2026-02-10T10:20:00",
            "payload": {"updates": {"status": "skipped"}},
        },
    ]

    signals = retrospective._detect_deviation_signals(events, days=7)
    repeated_skip = _signal_by_name(signals, "repeated_skip")
    l2_interruption = _signal_by_name(signals, "l2_interruption")

    assert repeated_skip["threshold"] == 3
    assert repeated_skip["active"] is False
    assert l2_interruption["threshold"] == 2
    assert l2_interruption["active"] is True


def test_guardian_l2_protection_uses_ratio_threshold_config(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "_build_l2_reference_maps",
        lambda: ({"g_l2": "L2_FLOURISHING"}, {"t1": "g_l2", "t2": "g_l2", "t3": "g_l2"}),
    )
    thresholds = {
        "repeated_skip": 2,
        "l2_interruption": 1,
        "stagnation_days": 3,
        "l2_protection_high": 0.9,
        "l2_protection_medium": 0.6,
    }
    events = [
        {
            "type": "task_updated",
            "timestamp": "2026-02-10T10:00:00",
            "payload": {"id": "t1", "updates": {"status": "completed"}},
        },
        {
            "type": "task_updated",
            "timestamp": "2026-02-10T10:20:00",
            "payload": {"id": "t2", "updates": {"status": "completed"}},
        },
        {
            "type": "task_updated",
            "timestamp": "2026-02-10T10:30:00",
            "payload": {"id": "t3", "updates": {"status": "skipped"}},
        },
    ]

    payload = retrospective._guardian_l2_protection(events, days=7, thresholds=thresholds)
    assert payload["ratio"] == 0.67
    assert payload["level"] == "medium"
    assert payload["thresholds"]["high"] == 0.9
    assert payload["thresholds"]["medium"] == 0.6


def test_build_response_includes_suggestion_sources_for_active_signals(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": datetime.now().isoformat(),
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [
                {
                    "name": "repeated_skip",
                    "active": True,
                    "severity": "medium",
                    "summary": "skip detected",
                    "count": 2,
                    "threshold": 2,
                    "evidence": [{"event_id": "evt_1"}],
                },
                {
                    "name": "stagnation",
                    "active": False,
                    "severity": "info",
                    "summary": "none",
                    "count": 0,
                    "threshold": 3,
                    "evidence": [],
                },
            ],
            "observations": ["skip detected"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")

    payload = retrospective.build_guardian_retrospective_response(days=7)
    assert payload["display"] is True
    assert payload["suggestion"] == "skip detected"
    assert len(payload["suggestion_sources"]) == 1
    assert payload["suggestion_sources"][0]["signal"] == "repeated_skip"


def test_build_response_requires_confirmation_for_ask_level(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": datetime.now().isoformat(),
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [
                {
                    "name": "repeated_skip",
                    "active": True,
                    "severity": "medium",
                    "summary": "skip detected",
                    "count": 2,
                    "threshold": 2,
                    "evidence": [],
                }
            ],
            "observations": ["skip detected"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "ASK")
    monkeypatch.setattr(retrospective, "load_events_for_period", lambda days: [])

    payload = retrospective.build_guardian_retrospective_response(days=7)
    assert payload["display"] is True
    assert payload["require_confirm"] is True
    assert payload["confirmation_action"]["required"] is True
    assert payload["confirmation_action"]["confirmed"] is False
    assert payload["confirmation_action"]["endpoint"] == "/api/v1/retrospective/confirm"


def test_build_response_marks_confirmed_when_matching_event_exists(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": datetime.now().isoformat(),
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [
                {
                    "name": "repeated_skip",
                    "active": True,
                    "severity": "medium",
                    "summary": "skip detected",
                    "count": 2,
                    "threshold": 2,
                    "evidence": [],
                }
            ],
            "observations": ["skip detected"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "ASK")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_test")
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_confirmed",
                "timestamp": "2026-02-11T12:00:00",
                "payload": {"days": 7, "fingerprint": "gcf_test"},
            }
        ],
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    assert payload["require_confirm"] is False
    assert payload["confirmation_action"]["required"] is True
    assert payload["confirmation_action"]["confirmed"] is True
    assert payload["confirmation_action"]["confirmed_at"] == "2026-02-11T12:00:00"
