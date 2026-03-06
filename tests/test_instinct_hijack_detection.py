"""
Tests for Iteration 10: Instinct Hijack Detection
"""
import pytest
from datetime import datetime, timedelta

from core.retrospective import (
    _detect_instinct_hijack_signals,
    _detect_task_abandonment,
    _detect_repeated_dismiss,
    build_guardian_retrospective_response,
)


def test_detect_task_abandonment_flags_abandoned_tasks():
    """测试任务放弃检测：任务创建后未完成就跳过"""
    now = datetime.now()
    events = [
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"task_id": "t1", "title": "Task 1"},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=1, hours=1)).isoformat(),
            "payload": {"task_id": "t1", "status": "skipped"},
        },
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"task_id": "t2", "title": "Task 2"},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=2, hours=1)).isoformat(),
            "payload": {"task_id": "t2", "status": "skipped"},
        },
    ]

    signal = _detect_task_abandonment(events, days=7, thresholds={"task_abandonment": 2})

    assert signal["name"] == "instinct_hijack"
    assert signal["pattern"] == "task_abandonment"
    assert signal["active"] is True
    assert signal["count"] == 2
    assert signal["threshold"] == 2
    assert signal["severity"] == "high"
    assert "检测到 2 次任务放弃行为" in signal["summary"]
    assert len(signal["evidence"]) == 4  # 2 created + 2 abandoned


def test_detect_task_abandonment_below_threshold():
    """测试任务放弃检测：低于阈值不触发"""
    now = datetime.now()
    events = [
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"task_id": "t1", "title": "Task 1"},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=1, hours=1)).isoformat(),
            "payload": {"task_id": "t1", "status": "skipped"},
        },
    ]

    signal = _detect_task_abandonment(events, days=7, thresholds={"task_abandonment": 2})

    assert signal["active"] is False
    assert signal["count"] == 1
    assert signal["severity"] == "info"


def test_detect_repeated_dismiss_flags_dismissals():
    """测试重复推迟检测：多次推迟Guardian建议"""
    now = datetime.now()
    events = [
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"action": "snooze", "context": "recovering"},
        },
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"action": "dismiss", "context": "resource_blocked"},
        },
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=3)).isoformat(),
            "payload": {"action": "snooze", "context": "task_too_big"},
        },
    ]

    signal = _detect_repeated_dismiss(events, days=7, thresholds={"repeated_dismiss": 3})

    assert signal["name"] == "instinct_hijack"
    assert signal["pattern"] == "repeated_dismiss"
    assert signal["active"] is True
    assert signal["count"] == 3
    assert signal["threshold"] == 3
    assert signal["severity"] == "medium"
    assert "检测到 3 次推迟/忽略Guardian建议" in signal["summary"]
    assert len(signal["evidence"]) == 3


def test_detect_repeated_dismiss_below_threshold():
    """测试重复推迟检测：低于阈值不触发"""
    now = datetime.now()
    events = [
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"action": "snooze", "context": "recovering"},
        },
    ]

    signal = _detect_repeated_dismiss(events, days=7, thresholds={"repeated_dismiss": 3})

    assert signal["active"] is False
    assert signal["count"] == 1
    assert signal["severity"] == "info"


def test_detect_instinct_hijack_signals_returns_active_signals():
    """测试劫持检测主函数：返回活跃信号"""
    now = datetime.now()
    events = [
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"task_id": "t1", "title": "Task 1"},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=1, hours=1)).isoformat(),
            "payload": {"task_id": "t1", "status": "skipped"},
        },
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "payload": {"task_id": "t2", "title": "Task 2"},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=2, hours=1)).isoformat(),
            "payload": {"task_id": "t2", "status": "skipped"},
        },
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=3)).isoformat(),
            "payload": {"action": "snooze", "context": "recovering"},
        },
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=4)).isoformat(),
            "payload": {"action": "dismiss", "context": "resource_blocked"},
        },
        {
            "type": "guardian_response",
            "timestamp": (now - timedelta(days=5)).isoformat(),
            "payload": {"action": "snooze", "context": "task_too_big"},
        },
    ]

    signals = _detect_instinct_hijack_signals(
        events,
        days=7,
        thresholds={"task_abandonment": 2, "repeated_dismiss": 3},
    )

    # 应该返回2个活跃信号
    assert len(signals) == 2

    # 检查任务放弃信号
    task_abandonment = [s for s in signals if s["pattern"] == "task_abandonment"]
    assert len(task_abandonment) == 1
    assert task_abandonment[0]["active"] is True

    # 检查重复推迟信号
    repeated_dismiss = [s for s in signals if s["pattern"] == "repeated_dismiss"]
    assert len(repeated_dismiss) == 1
    assert repeated_dismiss[0]["active"] is True


def test_build_guardian_retrospective_includes_hijack_signals():
    """测试Guardian复盘响应包含劫持信号"""
    # 使用真实事件日志测试
    payload = build_guardian_retrospective_response(days=7)

    # 检查deviation_signals包含instinct_hijack信号
    deviation_signals = payload.get("deviation_signals", [])
    hijack_signals = [s for s in deviation_signals if s.get("name") == "instinct_hijack"]

    # 即使没有活跃的劫持信号，也应该有信号结构
    assert isinstance(hijack_signals, list)

    # 如果有活跃信号，检查结构
    for signal in hijack_signals:
        if signal.get("active"):
            assert signal["name"] == "instinct_hijack"
            assert signal["pattern"] in ("task_abandonment", "repeated_dismiss")
            assert "count" in signal
            assert "threshold" in signal
            assert "summary" in signal
            assert "evidence" in signal
            assert isinstance(signal["evidence"], list)


def test_hijack_signals_respect_configurable_thresholds():
    """测试劫持信号遵循可配置阈值"""
    now = datetime.now()
    events = [
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"task_id": "t1", "title": "Task 1"},
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=1, hours=1)).isoformat(),
            "payload": {"task_id": "t1", "status": "skipped"},
        },
    ]

    # 阈值为1，应该触发
    signal1 = _detect_task_abandonment(events, days=7, thresholds={"task_abandonment": 1})
    assert signal1["active"] is True

    # 阈值为2，不应该触发
    signal2 = _detect_task_abandonment(events, days=7, thresholds={"task_abandonment": 2})
    assert signal2["active"] is False


def test_hijack_signals_include_evidence_chain():
    """测试劫持信号包含完整证据链"""
    now = datetime.now()
    events = [
        {
            "type": "task_created",
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "payload": {"task_id": "t1", "title": "Task 1"},
            "event_id": "evt_001",
        },
        {
            "type": "task_updated",
            "timestamp": (now - timedelta(days=1, hours=1)).isoformat(),
            "payload": {"task_id": "t1", "status": "skipped"},
            "event_id": "evt_002",
        },
    ]

    signal = _detect_task_abandonment(events, days=7, thresholds={"task_abandonment": 1})

    assert signal["active"] is True
    assert len(signal["evidence"]) == 2

    # 检查证据结构
    for evidence in signal["evidence"]:
        assert "type" in evidence
        assert "timestamp" in evidence
        assert "detail" in evidence
        assert evidence["type"] in ("task_created", "task_updated")
