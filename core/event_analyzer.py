"""
Event Analyzer Module for Guardian System.

This module contains all event analysis functions for the Guardian system,
including event loading, completion statistics, failure pattern identification,
and activity trend calculation.

Phase 2 of retrospective.py refactoring.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.event_sourcing import EVENT_LOG_PATH


def load_events_for_period(days: int = 7) -> List[Dict[str, Any]]:
    """
    Load events for the specified period.

    Args:
        days: Number of days to look back (default: 7 for weekly report)

    Returns:
        List of event dictionaries.
    """
    if not EVENT_LOG_PATH.exists():
        return []

    cutoff_date = datetime.now() - timedelta(days=days)
    events = []

    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                timestamp_str = event.get("timestamp", "")
                if timestamp_str:
                    try:
                        event_time = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        if event_time.replace(tzinfo=None) >= cutoff_date:
                            events.append(event)
                    except ValueError:
                        events.append(event)
                else:
                    events.append(event)
            except json.JSONDecodeError:
                continue

    return events


def analyze_completion_stats(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze task completion statistics.

    Returns:
        Statistics dictionary with completion rates and counts.
    """
    stats = {
        "total_tasks": 0,
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "blocked": 0,
        "completion_rate": 0.0,
        "by_priority": defaultdict(lambda: {"completed": 0, "failed": 0})
    }

    for event in events:
        event_type = event.get("type", "")

        if event_type == "task_completed":
            stats["total_tasks"] += 1
            stats["completed"] += 1

        elif event_type == "task_failed":
            stats["total_tasks"] += 1
            stats["failed"] += 1

            failure_type = event.get("failure_type", "unknown")
            if failure_type == "skipped":
                stats["skipped"] += 1
            elif failure_type == "blocked":
                stats["blocked"] += 1

    # 计算完成率
    if stats["total_tasks"] > 0:
        stats["completion_rate"] = round(
            stats["completed"] / stats["total_tasks"], 2
        )

    # 转换 defaultdict
    stats["by_priority"] = dict(stats["by_priority"])

    return stats


def identify_failure_patterns(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify recurring failure patterns.

    Returns:
        List of identified patterns with suggestions.
    """
    patterns = []
    failure_reasons = defaultdict(list)

    for event in events:
        if event.get("type") != "task_failed":
            continue

        task_id = event.get("task_id", "")
        reason = event.get("reason", "")
        failure_type = event.get("failure_type", "unknown")

        failure_reasons[failure_type].append({
            "task_id": task_id,
            "reason": reason
        })

    # 分析模式
    for failure_type, failures in failure_reasons.items():
        if len(failures) >= 2:  # 至少 2 次才算模式（经验值）
            pattern = {
                "type": failure_type,
                "count": len(failures),
                "tasks": [f["task_id"] for f in failures[:5]],  # 最多显示 5 个
                "suggestion": _get_failure_suggestion(failure_type)
            }
            patterns.append(pattern)

    return patterns


def _get_failure_suggestion(failure_type: str) -> str:
    """Get improvement suggestion for a failure type."""
    suggestions = {
        "skipped": "考虑将这类任务拆分为更小的步骤，或调整优先级",
        "blocked": "识别外部依赖，尝试提前准备或寻找替代方案",
        "timeout": "重新评估时间分配，或选择更合适的执行时段",
        "invalid_plan": "改进计划生成逻辑，确保任务具体可执行"
    }
    return suggestions.get(failure_type, "分析具体原因并调整策略")


def calculate_activity_trend(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calculate daily activity trend.

    Returns:
        Dict mapping date strings to event counts.
    """
    daily_counts = defaultdict(int)

    for event in events:
        timestamp_str = event.get("timestamp", "")
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                daily_counts[date_str] += 1
            except ValueError:
                continue

    return dict(daily_counts)


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


def _event_evidence(event: Dict[str, Any], detail: str) -> Dict[str, Any]:
    """Build evidence dict from event."""
    return {
        "event_id": event.get("event_id"),
        "type": event.get("type"),
        "timestamp": event.get("timestamp"),
        "detail": detail,
    }
