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


def test_detect_deviation_signals_includes_l2_session_interruptions():
    events = [
        {
            "event_id": "evt_l2_interrupt_1",
            "type": "l2_session_interrupted",
            "timestamp": "2026-02-10T10:05:00",
            "payload": {"session_id": "s1", "reason": "external_interrupt"},
        }
    ]
    thresholds = {
        "repeated_skip": 2,
        "l2_interruption": 1,
        "stagnation_days": 3,
        "l2_protection_high": 0.75,
        "l2_protection_medium": 0.50,
    }

    signals = retrospective._detect_deviation_signals(events, days=7, thresholds=thresholds)
    l2_interruption = _signal_by_name(signals, "l2_interruption")

    assert l2_interruption["active"] is True
    assert l2_interruption["count"] == 1
    assert l2_interruption["evidence"]
    assert "interrupted" in l2_interruption["evidence"][0]["detail"]


def test_guardian_l2_session_snapshot_tracks_active_and_latest():
    events = [
        {
            "type": "l2_session_started",
            "timestamp": "2026-02-10T09:00:00",
            "payload": {"session_id": "s1"},
        },
        {
            "type": "l2_session_interrupted",
            "timestamp": "2026-02-10T09:20:00",
            "payload": {"session_id": "s1", "reason": "energy_drop"},
        },
        {
            "type": "l2_session_started",
            "timestamp": "2026-02-10T10:00:00",
            "payload": {"session_id": "s2"},
        },
    ]

    snapshot = retrospective._guardian_l2_session(events)
    assert snapshot["started"] == 2
    assert snapshot["interrupted"] == 1
    assert snapshot["active_session"] is True
    assert snapshot["active_session_id"] == "s2"
    assert snapshot["latest"]["type"] == "l2_session_started"
    assert snapshot["recent_events"]


def test_guardian_l2_session_snapshot_tracks_resume_and_micro_ritual():
    events = [
        {
            "type": "l2_session_started",
            "timestamp": "2026-02-10T09:00:00",
            "payload": {"session_id": "s1", "intention": "Ship one meaningful milestone"},
        },
        {
            "type": "l2_session_interrupted",
            "timestamp": "2026-02-10T09:20:00",
            "payload": {"session_id": "s1", "reason": "external_interrupt"},
        },
        {
            "type": "l2_session_resumed",
            "timestamp": "2026-02-10T09:35:00",
            "payload": {"session_id": "s1", "resume_step": "Reopen notes and execute next 10m"},
        },
        {
            "type": "l2_session_completed",
            "timestamp": "2026-02-10T10:05:00",
            "payload": {"session_id": "s1", "reflection": "Closed one long-term output"},
        },
    ]

    snapshot = retrospective._guardian_l2_session(events)
    assert snapshot["started"] == 1
    assert snapshot["resumed"] == 1
    assert snapshot["completed"] == 1
    assert snapshot["interrupted"] == 1
    assert snapshot["recovery_rate"] == 1.0
    assert snapshot["resume_ready"] is False
    assert snapshot["micro_ritual"]["started_with_intention"] == 1
    assert snapshot["micro_ritual"]["completed_with_reflection"] == 1
    assert snapshot["micro_ritual"]["start_intention_rate"] == 1.0
    assert snapshot["micro_ritual"]["completion_reflection_rate"] == 1.0
    assert any("resumed" in ev["detail"] for ev in snapshot["recent_events"])


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
        "_guardian_l2_session",
        lambda events: {
            "started": 1,
            "completed": 1,
            "interrupted": 0,
            "completion_rate": 1.0,
            "active_session": False,
            "active_session_id": None,
            "latest": {"type": "l2_session_completed"},
            "recent_events": [],
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
    assert payload["l2_session"]["completed"] == 1


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


def test_build_response_includes_response_action_latest(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": datetime.now().isoformat(),
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_resp")
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:00:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_resp",
                    "action": "dismiss",
                    "context": "instinct_escape",
                },
            }
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    assert payload["response_action"]["endpoint"] == "/api/v1/retrospective/respond"
    assert payload["response_action"]["fingerprint"] == "gcf_resp"
    assert payload["response_action"]["latest"]["action"] == "dismiss"
    assert payload["response_action"]["latest"]["context"] == "instinct_escape"
    assert set(payload["response_action"]["allowed_actions"]) == {"confirm", "snooze", "dismiss"}
    assert set(payload["response_action"]["allowed_contexts"]) == {
        "recovering",
        "resource_blocked",
        "task_too_big",
        "instinct_escape",
    }
    assert payload["l2_session_action"]["start"]["endpoint"] == "/api/v1/l2/session/start"
    assert payload["l2_session_action"]["resume"]["endpoint"] == "/api/v1/l2/session/resume"
    assert payload["l2_session_action"]["interrupt"]["endpoint"] == "/api/v1/l2/session/interrupt"
    assert payload["l2_session_action"]["complete"]["endpoint"] == "/api/v1/l2/session/complete"
    assert payload["l2_session_action"]["ritual"]["start_intention_prompt"]
    assert payload["l2_session_action"]["ritual"]["complete_reflection_prompt"]
    assert payload["guardian_role"]["representing"] == "BLUEPRINT_SELF"
    assert payload["guardian_role"]["facing"] == "INSTINCT_SELF"


def test_build_response_maps_recovering_context_to_reflective_role(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": datetime.now().isoformat(),
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_role")
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:00:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_role",
                    "action": "snooze",
                    "context": "recovering",
                },
            }
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    assert payload["response_action"]["latest"]["context"] == "recovering"
    assert payload["guardian_role"]["representing"] == "BLUEPRINT_SELF"
    assert payload["guardian_role"]["facing"] == "REFLECTIVE_SELF"
    assert payload["guardian_role"]["mode"] == "support_recovery"


def test_authority_escalation_stage_uses_resistance_counts(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": "2026-02-11T12:00:00",
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_stage")
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 2,
            "l2_interruption": 1,
            "stagnation_days": 3,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.5,
            "escalation_window_days": 7,
            "escalation_firm_resistance": 2,
            "escalation_periodic_resistance": 4,
            "safe_mode_enabled": False,
            "safe_mode_resistance_threshold": 5,
            "safe_mode_min_response_events": 3,
            "safe_mode_max_confirmation_ratio": 0.34,
            "safe_mode_recovery_confirmations": 2,
            "safe_mode_cooldown_hours": 24,
        },
    )
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:00:00",
                "payload": {"days": 7, "fingerprint": "gcf_stage", "action": "dismiss"},
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:10:00",
                "payload": {"days": 7, "fingerprint": "gcf_stage", "action": "snooze"},
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:20:00",
                "payload": {"days": 7, "fingerprint": "gcf_stage", "action": "dismiss"},
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:30:00",
                "payload": {"days": 7, "fingerprint": "gcf_stage", "action": "dismiss"},
            },
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    assert payload["authority"]["escalation"]["stage"] == "periodic_check"
    assert payload["authority"]["escalation"]["resistance_count"] == 4


def test_authority_safe_mode_recommendation_can_enter(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": "2026-02-11T12:00:00",
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_safe")
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 2,
            "l2_interruption": 1,
            "stagnation_days": 3,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.5,
            "escalation_window_days": 7,
            "escalation_firm_resistance": 2,
            "escalation_periodic_resistance": 4,
            "safe_mode_enabled": True,
            "safe_mode_resistance_threshold": 3,
            "safe_mode_min_response_events": 3,
            "safe_mode_max_confirmation_ratio": 0.34,
            "safe_mode_recovery_confirmations": 2,
            "safe_mode_cooldown_hours": 24,
        },
    )
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:00:00",
                "payload": {"days": 7, "fingerprint": "gcf_safe", "action": "dismiss"},
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:10:00",
                "payload": {"days": 7, "fingerprint": "gcf_safe", "action": "dismiss"},
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T09:20:00",
                "payload": {"days": 7, "fingerprint": "gcf_safe", "action": "snooze"},
            },
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    recommendation = payload["authority"]["safe_mode"]["recommendation"]
    assert recommendation["should_enter"] is True
    assert recommendation["reason"] == "high_resistance_low_follow_through"


def test_build_response_includes_humanization_metrics_and_explainability(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": "2026-02-11T12:00:00",
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": True, "delay_signals": False, "summary": "friction"},
            "l2_protection": {"ratio": 0.5, "level": "medium", "summary": "moderate"},
            "l2_session": {
                "started": 1,
                "completed": 0,
                "interrupted": 1,
                "completion_rate": 0.0,
                "active_session": False,
                "active_session_id": None,
                "latest": None,
                "recent_events": [],
            },
            "deviation_signals": [
                {
                    "name": "repeated_skip",
                    "active": True,
                    "severity": "medium",
                    "summary": "skip",
                    "count": 2,
                    "threshold": 2,
                    "evidence": [],
                },
                {
                    "name": "l2_interruption",
                    "active": True,
                    "severity": "high",
                    "summary": "l2",
                    "count": 1,
                    "threshold": 1,
                    "evidence": [],
                },
                {
                    "name": "stagnation",
                    "active": True,
                    "severity": "medium",
                    "summary": "stagnation",
                    "count": 4,
                    "threshold": 3,
                    "evidence": [],
                },
            ],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_human")
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 2,
            "l2_interruption": 1,
            "stagnation_days": 3,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.5,
            "escalation_window_days": 7,
            "escalation_firm_resistance": 2,
            "escalation_periodic_resistance": 4,
            "safe_mode_enabled": False,
            "safe_mode_resistance_threshold": 5,
            "safe_mode_min_response_events": 3,
            "safe_mode_max_confirmation_ratio": 0.34,
            "safe_mode_recovery_confirmations": 2,
            "safe_mode_cooldown_hours": 24,
        },
    )
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "task_recovery_suggested",
                "timestamp": "2026-02-11T08:00:00",
                "payload": {"recovery_task_id": "t_recovery_1"},
            },
            {
                "type": "task_updated",
                "timestamp": "2026-02-11T09:00:00",
                "payload": {"id": "t_recovery_1", "updates": {"status": "completed"}},
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T10:00:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_human",
                    "action": "dismiss",
                    "context": "instinct_escape",
                    "recovery_step": "Take the minimal next step now.",
                },
            },
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    metrics = payload["humanization_metrics"]
    trust_calibration = metrics["trust_calibration"]

    assert metrics["recovery_adoption_rate"]["rate"] == 1.0
    assert metrics["friction_load"]["level"] == "high"
    assert metrics["support_vs_override"]["override_count"] == 1
    assert trust_calibration["perceived_control_score"]["status"] == "ready"
    assert trust_calibration["interruption_burden_rate"]["status"] == "ready"
    assert trust_calibration["recovery_time_to_resume_minutes"]["status"] == "unavailable"
    assert trust_calibration["mundane_time_saved_hours"]["status"] == "ready"
    assert payload["north_star_metrics"]["window_days"] == 7
    assert "mundane_automation_coverage" in payload["north_star_metrics"]
    assert "human_trust_index" in payload["north_star_metrics"]
    assert "blueprint_narrative" in payload
    assert payload["blueprint_narrative"]["narrative_card"]["reinforce_behavior"]
    assert payload["blueprint_narrative"]["narrative_card"]["reduce_behavior"]
    assert payload["explainability"]["why_this_suggestion"].startswith(
        "Suggestion is triggered by:"
    )
    assert "Next suggested recovery step" in payload["explainability"]["what_happens_next"]


def test_humanization_metrics_trust_calibration_recovers_l2_resume_time():
    events = [
        {
            "type": "task_recovery_suggested",
            "timestamp": "2026-02-11T08:00:00",
            "payload": {"recovery_task_id": "t_recovery_1"},
        },
        {
            "type": "task_updated",
            "timestamp": "2026-02-11T08:05:00",
            "payload": {"id": "t_recovery_1", "updates": {"status": "completed"}},
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": "2026-02-11T08:10:00",
            "payload": {"days": 7, "action": "confirm", "context": "recovering"},
        },
        {
            "type": "l2_session_interrupted",
            "timestamp": "2026-02-11T09:00:00",
            "payload": {"session_id": "s1", "reason": "external_interrupt"},
        },
        {
            "type": "l2_session_resumed",
            "timestamp": "2026-02-11T09:12:00",
            "payload": {"session_id": "s1"},
        },
    ]

    metrics = retrospective._guardian_humanization_metrics(
        events=events,
        days=7,
        deviation_signals=[],
    )
    trust_calibration = metrics["trust_calibration"]

    assert trust_calibration["perceived_control_score"]["status"] == "ready"
    assert trust_calibration["interruption_burden_rate"]["status"] == "ready"
    assert trust_calibration["recovery_time_to_resume_minutes"]["status"] == "ready"
    assert trust_calibration["recovery_time_to_resume_minutes"]["median_minutes"] == 12
    assert trust_calibration["mundane_time_saved_hours"]["status"] == "ready"
    assert trust_calibration["mundane_time_saved_hours"]["hours"] == 0.25


def test_humanization_metrics_trust_calibration_returns_unavailable_without_data():
    metrics = retrospective._guardian_humanization_metrics(
        events=[],
        days=7,
        deviation_signals=[],
    )
    trust_calibration = metrics["trust_calibration"]

    assert trust_calibration["perceived_control_score"]["status"] == "unavailable"
    assert trust_calibration["interruption_burden_rate"]["status"] == "unavailable"
    assert trust_calibration["recovery_time_to_resume_minutes"]["status"] == "unavailable"
    assert trust_calibration["mundane_time_saved_hours"]["status"] == "unavailable"


def test_intervention_policy_suppresses_repeated_prompts_with_budget(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": "2026-02-11T12:00:00",
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": True, "delay_signals": False, "summary": "friction"},
            "l2_protection": {"ratio": 0.6, "level": "medium", "summary": "moderate"},
            "l2_session": {"active_session": False, "active_session_id": None},
            "deviation_signals": [
                {
                    "name": "repeated_skip",
                    "active": True,
                    "severity": "medium",
                    "summary": "skip",
                    "count": 2,
                    "threshold": 2,
                    "evidence": [],
                }
            ],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_budget")
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 2,
            "l2_interruption": 1,
            "stagnation_days": 3,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.5,
            "escalation_window_days": 7,
            "escalation_firm_resistance": 2,
            "escalation_periodic_resistance": 4,
            "safe_mode_enabled": True,
            "safe_mode_resistance_threshold": 5,
            "safe_mode_min_response_events": 3,
            "safe_mode_max_confirmation_ratio": 0.34,
            "safe_mode_recovery_confirmations": 2,
            "safe_mode_cooldown_hours": 24,
            "reminder_budget_window_hours": 6,
            "reminder_budget_max_prompts": 2,
            "reminder_budget_enforce": True,
            "cadence_support_recovery_cooldown_hours": 8,
            "cadence_override_cooldown_hours": 3,
            "cadence_observe_cooldown_hours": 12,
        },
    )
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:10:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_budget",
                    "action": "snooze",
                    "context": "recovering",
                },
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:20:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_budget",
                    "action": "dismiss",
                    "context": "recovering",
                },
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:30:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_budget",
                    "action": "snooze",
                    "context": "recovering",
                },
            },
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    policy = payload["intervention_policy"]
    budget = policy["friction_budget"]

    assert policy["mode"] == "support_recovery"
    assert budget["suppressed"] is True
    assert budget["budget_exceeded"] is True
    assert payload["display"] is False
    assert payload["suggestion"] == ""
    assert payload["explainability"]["why_now"]


def test_intervention_policy_switches_to_trust_repair_on_consecutive_rejection_or_rollback(
    monkeypatch,
):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": "2026-02-11T13:00:00",
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": True, "delay_signals": False, "summary": "friction"},
            "l2_protection": {"ratio": 0.6, "level": "medium", "summary": "moderate"},
            "l2_session": {"active_session": False, "active_session_id": None},
            "deviation_signals": [
                {
                    "name": "repeated_skip",
                    "active": True,
                    "severity": "medium",
                    "summary": "skip",
                    "count": 2,
                    "threshold": 2,
                    "evidence": [],
                }
            ],
            "observations": ["keep focus"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "ASK")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_trust")
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 2,
            "l2_interruption": 1,
            "stagnation_days": 3,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.5,
            "escalation_window_days": 7,
            "escalation_firm_resistance": 2,
            "escalation_periodic_resistance": 4,
            "safe_mode_enabled": True,
            "safe_mode_resistance_threshold": 5,
            "safe_mode_min_response_events": 3,
            "safe_mode_max_confirmation_ratio": 0.34,
            "safe_mode_recovery_confirmations": 2,
            "safe_mode_cooldown_hours": 24,
            "reminder_budget_window_hours": 6,
            "reminder_budget_max_prompts": 2,
            "reminder_budget_enforce": True,
            "trust_repair_window_hours": 48,
            "trust_repair_negative_streak": 2,
            "cadence_support_recovery_cooldown_hours": 8,
            "cadence_override_cooldown_hours": 3,
            "cadence_observe_cooldown_hours": 12,
            "cadence_trust_repair_cooldown_hours": 1,
        },
    )
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:10:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_trust",
                    "action": "dismiss",
                    "context": "instinct_escape",
                },
            },
            {
                "type": "guardian_autotune_rolled_back",
                "timestamp": "2026-02-11T12:20:00",
                "payload": {"proposal_id": "atp_1", "fingerprint": "gatfp_1"},
            },
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    policy = payload["intervention_policy"]
    trust_repair = policy["trust_repair"]

    assert policy["mode"] == "trust_repair"
    assert policy["intensity"] == "supportive"
    assert trust_repair["active"] is True
    assert trust_repair["negative_streak"] == 2
    assert trust_repair["autotune_rollback_count"] == 1
    assert payload["require_confirm"] is False
    assert "Trust-repair mode is active" in payload["explainability"]["what_happens_next"]


def test_intervention_policy_keeps_display_for_high_severity(monkeypatch):
    monkeypatch.setattr(
        retrospective,
        "generate_guardian_retrospective",
        lambda days: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": "2026-02-11T12:00:00",
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": True, "delay_signals": False, "summary": "friction"},
            "l2_protection": {"ratio": 0.3, "level": "low", "summary": "low"},
            "l2_session": {"active_session": False, "active_session_id": None},
            "deviation_signals": [
                {
                    "name": "l2_interruption",
                    "active": True,
                    "severity": "high",
                    "summary": "l2 interrupted",
                    "count": 2,
                    "threshold": 1,
                    "evidence": [],
                }
            ],
            "observations": ["protect L2 now"],
        },
    )
    monkeypatch.setattr(retrospective, "get_intervention_level", lambda: "SOFT")
    monkeypatch.setattr(retrospective, "_build_confirmation_fingerprint", lambda raw: "gcf_high")
    monkeypatch.setattr(
        retrospective,
        "_guardian_thresholds",
        lambda days: {
            "repeated_skip": 2,
            "l2_interruption": 1,
            "stagnation_days": 3,
            "l2_protection_high": 0.75,
            "l2_protection_medium": 0.5,
            "escalation_window_days": 7,
            "escalation_firm_resistance": 2,
            "escalation_periodic_resistance": 4,
            "safe_mode_enabled": True,
            "safe_mode_resistance_threshold": 5,
            "safe_mode_min_response_events": 3,
            "safe_mode_max_confirmation_ratio": 0.34,
            "safe_mode_recovery_confirmations": 2,
            "safe_mode_cooldown_hours": 24,
            "reminder_budget_window_hours": 6,
            "reminder_budget_max_prompts": 1,
            "reminder_budget_enforce": True,
            "cadence_support_recovery_cooldown_hours": 8,
            "cadence_override_cooldown_hours": 3,
            "cadence_observe_cooldown_hours": 12,
        },
    )
    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: [
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:10:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_high",
                    "action": "snooze",
                    "context": "recovering",
                },
            },
            {
                "type": "guardian_intervention_responded",
                "timestamp": "2026-02-11T11:20:00",
                "payload": {
                    "days": 7,
                    "fingerprint": "gcf_high",
                    "action": "dismiss",
                    "context": "recovering",
                },
            },
        ],
    )
    monkeypatch.setattr(
        retrospective,
        "_safe_mode_state_from_runtime",
        lambda: {"active": False, "entered_at": None, "exited_at": None, "reason": None},
    )

    payload = retrospective.build_guardian_retrospective_response(days=7)
    policy = payload["intervention_policy"]

    assert policy["mode"] == "focused_override"
    assert policy["friction_budget"]["suppressed"] is False
    assert payload["display"] is True
    assert payload["suggestion"] == "protect L2 now"
