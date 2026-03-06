"""
Tests for Iteration 12: Authority System Enhancement
"""
import pytest
from datetime import datetime, timedelta

from core.retrospective import (
    _get_last_escalation_stage,
    _guardian_authority_snapshot,
    build_guardian_retrospective_response,
)


def test_get_last_escalation_stage_returns_none_without_events():
    """测试无事件时返回None"""
    events = []
    window_start = datetime.now() - timedelta(days=7)
    result = _get_last_escalation_stage(events, window_start)
    assert result is None


def test_get_last_escalation_stage_finds_latest_stage():
    """测试找到最新的干预级别"""
    now = datetime.now()
    events = [
        {
            "type": "authority_escalation_changed",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"new_stage": "gentle_nudge"}
        },
        {
            "type": "authority_escalation_changed",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"new_stage": "firm_reminder"}
        },
    ]
    window_start = now - timedelta(days=7)
    result = _get_last_escalation_stage(events, window_start)
    assert result == "firm_reminder"


def test_get_last_escalation_stage_ignores_other_events():
    """测试忽略其他类型事件"""
    now = datetime.now()
    events = [
        {"type": "guardian_response", "timestamp": now.isoformat()},
        {
            "type": "authority_escalation_changed",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "payload": {"new_stage": "periodic_check"}
        },
    ]
    window_start = now - timedelta(days=7)
    result = _get_last_escalation_stage(events, window_start)
    assert result == "periodic_check"


def test_authority_snapshot_includes_thresholds():
    """测试Authority快照包含阈值信息"""
    events = []
    thresholds = {
        "escalation_window_days": 7,
        "escalation_firm_resistance": 2,
        "escalation_periodic_resistance": 4,
    }
    now = datetime.now()

    result = _guardian_authority_snapshot(events, thresholds, now)

    assert "escalation" in result
    escalation = result["escalation"]
    assert "stage" in escalation
    assert "resistance_count" in escalation
    assert "response_count" in escalation
    assert "firm_reminder_resistance" in escalation
    assert "periodic_check_resistance" in escalation
    assert escalation["firm_reminder_resistance"] == 2
    assert escalation["periodic_check_resistance"] == 4


def test_escalation_stage_transitions_correctly():
    """测试干预级别正确转换"""
    now = datetime.now()
    
    # 测试 gentle_nudge (resistance_count < 2)
    events_low = [
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"action": "confirm"}
        }
    ]
    thresholds = {
        "escalation_firm_resistance": 2,
        "escalation_periodic_resistance": 4,
    }
    result_low = _guardian_authority_snapshot(events_low, thresholds, now)
    assert result_low["escalation"]["stage"] == "gentle_nudge"

    # 测试 firm_reminder (2 <= resistance_count < 4)
    events_medium = [
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"action": "dismiss"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"action": "snooze"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=3)).isoformat(),
            "payload": {"action": "dismiss"}
        },
    ]
    result_medium = _guardian_authority_snapshot(events_medium, thresholds, now)
    assert result_medium["escalation"]["stage"] == "firm_reminder"

    # 测试 periodic_check (resistance_count >= 4)
    events_high = [
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"action": "dismiss"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"action": "snooze"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=3)).isoformat(),
            "payload": {"action": "dismiss"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=4)).isoformat(),
            "payload": {"action": "snooze"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=5)).isoformat(),
            "payload": {"action": "dismiss"}
        },
    ]
    result_high = _guardian_authority_snapshot(events_high, thresholds, now)
    assert result_high["escalation"]["stage"] == "periodic_check"


def test_build_response_includes_escalation_thresholds():
    """测试复盘响应包含升级阈值"""
    payload = build_guardian_retrospective_response(days=7)

    authority = payload.get("authority", {})
    escalation = authority.get("escalation", {})

    assert "stage" in escalation
    assert "firm_reminder_resistance" in escalation
    assert "periodic_check_resistance" in escalation
    assert isinstance(escalation["firm_reminder_resistance"], int)
    assert isinstance(escalation["periodic_check_resistance"], int)


def test_escalation_change_appends_event(monkeypatch):
    """测试级别变化记录事件"""
    from core import event_sourcing

    # 模拟已有事件（包含旧的级别）
    now = datetime.now()
    events = [
        {
            "type": "authority_escalation_changed",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"new_stage": "gentle_nudge"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"action": "dismiss"}
        },
        {
            "type": "guardian_intervention_responded",
            "timestamp": (now - timedelta(hours=12)).isoformat(),
            "payload": {"action": "snooze"}
        },
    ]

    # 模拟 append_event
    appended_events = []
    def mock_append_event(event):
        appended_events.append(event)
    
    monkeypatch.setattr(event_sourcing, "append_event", mock_append_event)

    # 调用函数
    from core.retrospective import _guardian_authority_snapshot
    thresholds = {
        "escalation_firm_resistance": 2,
        "escalation_periodic_resistance": 4,
    }
    _guardian_authority_snapshot(events, thresholds, now)

    # 验证事件记录
    assert len(appended_events) == 1
    event = appended_events[0]
    assert event["type"] == "authority_escalation_changed"
    assert event["payload"]["old_stage"] == "gentle_nudge"
    assert event["payload"]["new_stage"] == "firm_reminder"
    assert event["payload"]["resistance_count"] == 2
    assert event["payload"]["trigger"] == "resistance_threshold_reached"
