from datetime import datetime, timedelta

import core.retrospective as retrospective


def test_guardian_north_star_metrics_v1_calculation(monkeypatch):
    now = datetime.now().replace(microsecond=0)

    suggestion_at = now - timedelta(days=1, hours=3)
    completion_at = suggestion_at + timedelta(hours=1)
    confirm_at = now - timedelta(days=1, hours=2)
    progress_at = confirm_at + timedelta(hours=1)
    current_l2_start = now - timedelta(days=2, hours=4)
    current_l2_end = current_l2_start + timedelta(hours=2)
    previous_l2_start = now - timedelta(days=9, hours=4)
    previous_l2_end = previous_l2_start + timedelta(hours=1)
    previous_alignment_at = now - timedelta(days=10)
    current_alignment_at = now - timedelta(days=2, hours=1)

    current_events = [
        {
            "type": "task_recovery_suggested",
            "timestamp": suggestion_at.isoformat(),
            "payload": {"recovery_task_id": "task_recovery_1"},
        },
        {
            "type": "task_updated",
            "timestamp": completion_at.isoformat(),
            "payload": {"id": "task_recovery_1", "updates": {"status": "completed"}},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"id": "task_skip_1", "updates": {"status": "skipped"}},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {
                "id": "task_overdue_1",
                "updates": {"scheduled_date": now.date().isoformat()},
                "meta": {"reason": "overdue_reschedule"},
            },
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=1, hours=1)).isoformat(),
            "payload": {"days": 7, "fingerprint": "gcf_ns", "action": "snooze"},
        },
        {
            "type": "guardian_intervention_confirmed",
            "timestamp": confirm_at.isoformat(),
            "payload": {"days": 7, "fingerprint": "gcf_ns"},
        },
        {
            "type": "progress_updated",
            "timestamp": progress_at.isoformat(),
            "payload": {"message": "follow through"},
        },
        {
            "type": "l2_session_started",
            "timestamp": current_l2_start.isoformat(),
            "payload": {"session_id": "s_current"},
        },
        {
            "type": "l2_session_completed",
            "timestamp": current_l2_end.isoformat(),
            "payload": {"session_id": "s_current"},
        },
        {
            "type": "goal_action",
            "goal_id": "goal_current",
            "timestamp": current_alignment_at.isoformat(),
            "payload": {"node": {"alignment_score": 80.0}},
        },
    ]
    lookback_events = current_events + [
        {
            "type": "l2_session_started",
            "timestamp": previous_l2_start.isoformat(),
            "payload": {"session_id": "s_previous"},
        },
        {
            "type": "l2_session_completed",
            "timestamp": previous_l2_end.isoformat(),
            "payload": {"session_id": "s_previous"},
        },
        {
            "type": "goal_action",
            "goal_id": "goal_previous",
            "timestamp": previous_alignment_at.isoformat(),
            "payload": {"node": {"alignment_score": 60.0}},
        },
    ]

    monkeypatch.setattr(
        retrospective,
        "load_events_for_period",
        lambda days: lookback_events if days >= 14 else current_events,
    )

    metrics = retrospective._guardian_north_star_metrics(
        events=current_events,
        days=7,
        humanization_metrics={
            "support_vs_override": {"support_ratio": 1.0},
            "friction_load": {"score": 0.0},
        },
    )

    assert metrics["window_days"] == 7

    mundane = metrics["mundane_automation_coverage"]
    assert mundane["l1_recovery_opportunities"] == 3
    assert mundane["adopted_auto_recovery"] == 1
    assert mundane["rate"] == 0.33
    assert mundane["met_target"] is False

    l2_bloom = metrics["l2_bloom_hours"]
    assert l2_bloom["hours"] == 2.0
    assert l2_bloom["baseline_hours"] == 1.0
    assert l2_bloom["delta_ratio"] == 1.0
    assert l2_bloom["met_target"] is True

    trust = metrics["human_trust_index"]
    assert trust["components"]["adoption_rate"] == 1.0
    assert trust["score"] == 1.0
    assert trust["met_target"] is True

    alignment = metrics["alignment_delta_weekly"]
    assert alignment["current_week_avg"] == 80.0
    assert alignment["previous_week_avg"] == 60.0
    assert alignment["delta"] == 20.0
    assert alignment["met_target"] is True

    assert metrics["targets_met"]["met_count"] == 3
    assert metrics["targets_met"]["total"] == 4
