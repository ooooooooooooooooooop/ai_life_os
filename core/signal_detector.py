"""
Signal Detection Module for Guardian System.

This module contains all signal detection functions for the Guardian system,
including behavior deviation signals and instinct hijack signals.

Phase 1 of retrospective.py refactoring.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config_manager import config


# L2 Session Interrupt Reason Labels
L2_SESSION_INTERRUPT_REASON_LABELS = {
    "emergency": "紧急情况",
    "external_interruption": "外部中断",
    "user_choice": "用户选择",
    "system_error": "系统错误",
    "other": "其他",
}


def _parse_event_time(event: Dict[str, Any]) -> Optional[datetime]:
    """Parse event timestamp to naive datetime."""
    timestamp_str = event.get("timestamp", "")
    if not timestamp_str:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def _phase_for_time(dt: datetime) -> str:
    """Map datetime to configured energy phase."""
    current_time = dt.strftime("%H:%M")
    for time_range, phase in config.ENERGY_PHASES.items():
        start_str, end_str = time_range.split("-")
        if start_str <= current_time < end_str:
            return phase
    return config.DEFAULT_ENERGY_PHASE


def _is_task_skip_event(event: Dict[str, Any]) -> bool:
    """Detect task skip-like events from event payload."""
    event_type = event.get("type")
    if event_type == "task_failed" and event.get("failure_type") == "skipped":
        return True
    if event_type != "task_updated":
        return False
    payload = event.get("payload") or {}
    updates = payload.get("updates", {}) if isinstance(payload, dict) else {}
    status = str(updates.get("status", "")).lower()
    return status == "skipped"


def _is_progress_event(event: Dict[str, Any]) -> bool:
    """Events that indicate forward progress."""
    event_type = event.get("type")
    if event_type in {"goal_completed", "progress_updated"}:
        return True
    if event_type == "execution_completed":
        outcome = str((event.get("payload") or {}).get("outcome", "")).lower()
        return outcome == "completed"
    if event_type != "task_updated":
        return False
    payload = event.get("payload") or {}
    updates = payload.get("updates", {}) if isinstance(payload, dict) else {}
    status = str(updates.get("status", "")).lower()
    return status == "completed"


def _event_evidence(event: Dict[str, Any], detail: str) -> Dict[str, Any]:
    """Build evidence dict from event."""
    return {
        "event_id": event.get("event_id"),
        "type": event.get("type"),
        "timestamp": event.get("timestamp"),
        "detail": detail,
    }


def _coerce_int(
    value: Any,
    default: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    """Coerce value to int with bounds."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _l2_interruption_evidence(
    events: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    """Build evidence for L2 interruption events."""
    evidence: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("type") == "l2_session_interrupted":
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            reason = str(payload.get("reason") or "other")
            reason_label = L2_SESSION_INTERRUPT_REASON_LABELS.get(reason, reason)
            detail = f"l2 session interrupted ({reason_label})"
        else:
            detail = f"skip during {_phase_for_time(_parse_event_time(ev) or now)}"
        evidence.append(_event_evidence(ev, detail))
    return evidence


def detect_deviation_signals(
    events: List[Dict[str, Any]],
    days: int,
    thresholds: Optional[Dict[str, Any]] = None,
    guardian_thresholds_func=None,
) -> List[Dict[str, Any]]:
    """
    Detect behavior deviation signals and provide traceable evidence.

    Args:
        events: List of events to analyze
        days: Analysis window in days
        thresholds: Optional threshold configuration
        guardian_thresholds_func: Function to get guardian thresholds

    Returns:
        List of deviation signals
    """
    skip_events: List[Dict[str, Any]] = []
    l2_interruptions: List[Dict[str, Any]] = []
    progress_events: List[Dict[str, Any]] = []

    for event in events:
        event_time = _parse_event_time(event)
        event_type = event.get("type")

        if _is_task_skip_event(event):
            skip_events.append(event)
            if event_time and _phase_for_time(event_time) == "deep_work":
                l2_interruptions.append(event)
        elif event_type == "l2_session_interrupted":
            l2_interruptions.append(event)

        if _is_progress_event(event):
            progress_events.append(event)

    if thresholds is None:
        if guardian_thresholds_func:
            thresholds = guardian_thresholds_func(days)
        else:
            thresholds = {}

    repeated_skip_threshold = _coerce_int(
        thresholds.get("repeated_skip"),
        default=2,
        min_value=1,
    )
    l2_interruption_threshold = _coerce_int(
        thresholds.get("l2_interruption"),
        default=1,
        min_value=1,
    )
    stagnation_threshold_days = _coerce_int(
        thresholds.get("stagnation_days"),
        default=(3 if days >= 3 else 1),
        min_value=1,
    )

    repeated_skip_count = len(skip_events)
    repeated_skip_active = repeated_skip_count >= repeated_skip_threshold

    l2_interruption_count = len(l2_interruptions)
    l2_interruption_active = l2_interruption_count >= l2_interruption_threshold

    now = datetime.now()
    recent_progress_time = max(
        (_parse_event_time(ev) for ev in progress_events if _parse_event_time(ev)),
        default=None,
    )
    if recent_progress_time is None:
        days_without_progress = days
    else:
        days_without_progress = max(0, (now - recent_progress_time).days)
    stagnation_active = days_without_progress >= stagnation_threshold_days

    signals = [
        {
            "name": "repeated_skip",
            "active": repeated_skip_active,
            "severity": "medium" if repeated_skip_active else "info",
            "count": repeated_skip_count,
            "threshold": repeated_skip_threshold,
            "summary": (
                f"检测到 {repeated_skip_count} 次跳过行为，可能存在执行摩擦。"
                if repeated_skip_active
                else "未检测到重复跳过行为。"
            ),
            "evidence": [
                _event_evidence(ev, "task skipped")
                for ev in skip_events[-3:]
            ],
        },
        {
            "name": "l2_interruption",
            "active": l2_interruption_active,
            "severity": "high" if l2_interruption_active else "info",
            "count": l2_interruption_count,
            "threshold": l2_interruption_threshold,
            "summary": (
                f"检测到 {l2_interruption_count} 次 L2 中断（深度时段跳过或会话中断）。"
                if l2_interruption_active
                else "未检测到深度工作时段中断信号。"
            ),
            "evidence": _l2_interruption_evidence(l2_interruptions[-3:], now),
        },
        {
            "name": "stagnation",
            "active": stagnation_active,
            "severity": "medium" if stagnation_active else "info",
            "count": days_without_progress,
            "threshold": stagnation_threshold_days,
            "summary": (
                f"最近 {days_without_progress} 天未观察到明确推进事件，存在停滞风险。"
                if stagnation_active
                else "近期推进节奏正常。"
            ),
            "evidence": (
                []
                if recent_progress_time is None
                else [
                    {
                        "event_id": None,
                        "type": "progress_marker",
                        "timestamp": recent_progress_time.isoformat(),
                        "detail": "latest progress timestamp",
                    }
                ]
            ),
        },
    ]

    # 接入 intervention_tracker：记录抵抗并写入干预级别
    from core.intervention_tracker import record_resistance, get_intervention_level
    for signal in signals:
        if signal.get("active"):
            key = signal.get("name", "unknown")
            record_resistance(key)
            signal["intervention_level"] = get_intervention_level(key)

    return signals


def detect_instinct_hijack_signals(
    events: List[Dict[str, Any]],
    days: int,
    thresholds: Optional[Dict[str, Any]] = None,
    guardian_thresholds_func=None,
) -> List[Dict[str, Any]]:
    """
    检测本能劫持信号（Iteration 10）。

    Args:
        events: 事件列表
        days: 分析时间窗口（天）
        thresholds: 阈值配置
        guardian_thresholds_func: Function to get guardian thresholds

    Returns:
        劫持信号列表，每个信号包含 name, pattern, active, severity, count, threshold, summary, evidence
    """
    if thresholds is None:
        if guardian_thresholds_func:
            thresholds = guardian_thresholds_func(days)
        else:
            thresholds = {}

    hijack_thresholds = thresholds.get("instinct_hijack", {})
    if not isinstance(hijack_thresholds, dict):
        hijack_thresholds = {}

    # 1. 检测任务放弃（Task Abandonment）
    task_abandonment_signal = _detect_task_abandonment(events, days, hijack_thresholds)

    # 2. 检测重复推迟建议（Repeated Dismiss）
    repeated_dismiss_signal = _detect_repeated_dismiss(events, days, hijack_thresholds)

    signals = [
        task_abandonment_signal,
        repeated_dismiss_signal,
    ]

    return [s for s in signals if s and s.get("active")]


def _detect_task_abandonment(
    events: List[Dict[str, Any]],
    days: int,
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """
    检测任务放弃行为：任务创建后未完成就跳过/删除。

    Args:
        events: 事件列表
        days: 分析时间窗口（天）
        thresholds: 阈值配置

    Returns:
        任务放弃信号
    """
    task_created_events = {}
    task_abandoned_events = []

    # 收集任务创建和放弃事件
    for event in events:
        event_type = event.get("type")
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue

        task_id = payload.get("task_id") or payload.get("id")
        if not task_id:
            continue

        if event_type == "task_created":
            task_created_events[task_id] = event
        elif event_type == "task_updated":
            status = payload.get("status")
            if status in ("skipped", "deleted"):
                # 检查是否有对应的创建事件
                if task_id in task_created_events:
                    task_abandoned_events.append({
                        "created": task_created_events[task_id],
                        "abandoned": event,
                    })

    # 统计放弃次数
    abandonment_count = len(task_abandoned_events)
    abandonment_threshold = _coerce_int(
        thresholds.get("task_abandonment"),
        default=2,
        min_value=1,
    )

    active = abandonment_count >= abandonment_threshold

    # 构建证据链
    evidence = []
    for item in task_abandoned_events[-3:]:  # 最多展示3个证据
        created_ev = item["created"]
        abandoned_ev = item["abandoned"]
        evidence.append(_event_evidence(created_ev, "task created"))
        evidence.append(_event_evidence(abandoned_ev, "task abandoned without completion"))

    return {
        "name": "instinct_hijack",
        "pattern": "task_abandonment",
        "active": active,
        "severity": "high" if active else "info",
        "count": abandonment_count,
        "threshold": abandonment_threshold,
        "summary": (
            f"检测到 {abandonment_count} 次任务放弃行为，可能存在逃避倾向。"
            if active
            else f"未检测到明显的任务放弃行为（{abandonment_count} 次）。"
        ),
        "evidence": evidence,
    }


def _detect_repeated_dismiss(
    events: List[Dict[str, Any]],
    days: int,
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """
    检测重复推迟/忽略Guardian建议的行为。

    Args:
        events: 事件列表
        days: 分析时间窗口（天）
        thresholds: 阈值配置

    Returns:
        重复推迟信号
    """
    dismiss_events = []

    # 收集guardian_response事件
    for event in events:
        event_type = event.get("type")
        if event_type != "guardian_response":
            continue

        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue

        action = payload.get("action")
        if action in ("snooze", "dismiss"):
            dismiss_events.append(event)

    # 统计推迟次数
    dismiss_count = len(dismiss_events)
    dismiss_threshold = _coerce_int(
        thresholds.get("repeated_dismiss"),
        default=3,
        min_value=1,
    )

    active = dismiss_count >= dismiss_threshold

    # 构建证据链
    evidence = [_event_evidence(ev, f"guardian suggestion {ev.get('payload', {}).get('action', 'dismissed')}")
                for ev in dismiss_events[-3:]]

    return {
        "name": "instinct_hijack",
        "pattern": "repeated_dismiss",
        "active": active,
        "severity": "medium" if active else "info",
        "count": dismiss_count,
        "threshold": dismiss_threshold,
        "summary": (
            f"检测到 {dismiss_count} 次推迟/忽略Guardian建议，可能存在对抗倾向。"
            if active
            else f"未检测到明显的对抗行为（{dismiss_count} 次推迟）。"
        ),
        "evidence": evidence,
    }
