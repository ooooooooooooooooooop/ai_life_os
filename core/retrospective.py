"""
Retrospective Engine for AI Life OS.

Generates execution reports and improvement suggestions.
Analyzes failure patterns and user behavior.

GuardianRetrospective: derived view from event_log (read-only), four dimensions:
rhythm, alignment, friction, observations.
"""
import json
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.config_manager import config
from core.event_sourcing import EVENT_LOG_PATH, rebuild_state
from core.llm_adapter import get_llm

GUARDIAN_RESPONSE_ACTIONS = {"confirm", "snooze", "dismiss"}
GUARDIAN_RESPONSE_CONTEXTS = (
    "recovering",
    "resource_blocked",
    "task_too_big",
    "instinct_escape",
)
GUARDIAN_RESPONSE_CONTEXT_LABELS = {
    "recovering": "恢复精力",
    "resource_blocked": "资源受阻",
    "task_too_big": "任务过大",
    "instinct_escape": "本能逃避",
}
GUARDIAN_RESPONSE_CONTEXT_HINTS = {
    "recovering": "先恢复状态，再继续推进。",
    "resource_blocked": "当前被资源或外部条件卡住。",
    "task_too_big": "先拆成最小下一步，降低启动阻力。",
    "instinct_escape": "正在被即时满足牵引，偏离长期价值。",
}
L2_SESSION_INTERRUPT_REASON_LABELS = {
    "context_switch": "上下文切换",
    "external_interrupt": "外部打断",
    "energy_drop": "精力下滑",
    "tooling_blocked": "工具阻塞",
    "other": "其他",
}
L2_SESSION_RESUME_HINTS = {
    "context_switch": "Spend 2 minutes restoring context, then run one 10-minute focus burst.",
    "external_interrupt": (
        "Close the interruption loop quickly and return with one minimal next step."
    ),
    "energy_drop": "Take a short recharge break and restart with the easiest valuable action.",
    "tooling_blocked": "Use a temporary workaround and keep momentum for one concrete output.",
    "other": (
        "Restart with a minimal next step and protect the next 10 minutes from context switching."
    ),
}


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
    return {
        "event_id": event.get("event_id"),
        "type": event.get("type"),
        "timestamp": event.get("timestamp"),
        "detail": detail,
    }


def _load_blueprint_config() -> Dict[str, Any]:
    config_path = Path(__file__).parent.parent / "config" / "blueprint.yaml"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _coerce_int(
    value: Any,
    default: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _coerce_float(
    value: Any,
    default: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _guardian_thresholds(days: int) -> Dict[str, Any]:
    defaults = {
        "repeated_skip": 2,
        "l2_interruption": 1,
        "stagnation_days": 3 if days >= 3 else 1,
        "l2_protection_high": 0.75,
        "l2_protection_medium": 0.50,
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
    }

    blueprint_config = _load_blueprint_config()
    raw_thresholds = blueprint_config.get("guardian_thresholds", {})
    if not isinstance(raw_thresholds, dict):
        raw_thresholds = {}

    deviation_raw = raw_thresholds.get("deviation_signals", {})
    if not isinstance(deviation_raw, dict):
        deviation_raw = {}

    l2_raw = raw_thresholds.get("l2_protection", {})
    if not isinstance(l2_raw, dict):
        l2_raw = {}

    authority_raw = blueprint_config.get("guardian_authority", {})
    if not isinstance(authority_raw, dict):
        authority_raw = {}

    escalation_raw = authority_raw.get("escalation", {})
    if not isinstance(escalation_raw, dict):
        escalation_raw = {}

    safe_mode_raw = authority_raw.get("safe_mode", {})
    if not isinstance(safe_mode_raw, dict):
        safe_mode_raw = {}
    cadence_raw = authority_raw.get("cadence", {})
    if not isinstance(cadence_raw, dict):
        cadence_raw = {}

    repeated_skip = _coerce_int(
        deviation_raw.get("repeated_skip", raw_thresholds.get("repeated_skip")),
        default=defaults["repeated_skip"],
        min_value=1,
    )
    l2_interruption = _coerce_int(
        deviation_raw.get("l2_interruption", raw_thresholds.get("l2_interruption")),
        default=defaults["l2_interruption"],
        min_value=1,
    )
    stagnation_days = _coerce_int(
        deviation_raw.get("stagnation_days", raw_thresholds.get("stagnation_days")),
        default=defaults["stagnation_days"],
        min_value=1,
    )
    high = _coerce_float(
        l2_raw.get("high", raw_thresholds.get("l2_protection_high")),
        default=defaults["l2_protection_high"],
        min_value=0.0,
        max_value=1.0,
    )
    medium = _coerce_float(
        l2_raw.get("medium", raw_thresholds.get("l2_protection_medium")),
        default=defaults["l2_protection_medium"],
        min_value=0.0,
        max_value=1.0,
    )
    if medium > high:
        medium = high

    escalation_window_days = _coerce_int(
        escalation_raw.get("window_days"),
        default=defaults["escalation_window_days"],
        min_value=1,
        max_value=30,
    )
    escalation_firm_resistance = _coerce_int(
        escalation_raw.get("firm_reminder_resistance"),
        default=defaults["escalation_firm_resistance"],
        min_value=1,
        max_value=99,
    )
    escalation_periodic_resistance = _coerce_int(
        escalation_raw.get("periodic_check_resistance"),
        default=defaults["escalation_periodic_resistance"],
        min_value=1,
        max_value=99,
    )
    if escalation_periodic_resistance < escalation_firm_resistance:
        escalation_periodic_resistance = escalation_firm_resistance

    safe_mode_enabled = _coerce_bool(
        safe_mode_raw.get("enabled"),
        defaults["safe_mode_enabled"],
    )
    safe_mode_resistance_threshold = _coerce_int(
        safe_mode_raw.get("resistance_threshold"),
        default=defaults["safe_mode_resistance_threshold"],
        min_value=1,
        max_value=999,
    )
    safe_mode_min_response_events = _coerce_int(
        safe_mode_raw.get("min_response_events"),
        default=defaults["safe_mode_min_response_events"],
        min_value=1,
        max_value=999,
    )
    safe_mode_max_confirmation_ratio = _coerce_float(
        safe_mode_raw.get("max_confirmation_ratio"),
        default=defaults["safe_mode_max_confirmation_ratio"],
        min_value=0.0,
        max_value=1.0,
    )
    safe_mode_recovery_confirmations = _coerce_int(
        safe_mode_raw.get("recovery_confirmations"),
        default=defaults["safe_mode_recovery_confirmations"],
        min_value=1,
        max_value=999,
    )
    safe_mode_cooldown_hours = _coerce_int(
        safe_mode_raw.get("cooldown_hours"),
        default=defaults["safe_mode_cooldown_hours"],
        min_value=1,
        max_value=720,
    )
    reminder_budget_window_hours = _coerce_int(
        cadence_raw.get("reminder_budget_window_hours"),
        default=defaults["reminder_budget_window_hours"],
        min_value=1,
        max_value=168,
    )
    reminder_budget_max_prompts = _coerce_int(
        cadence_raw.get("reminder_budget_max_prompts"),
        default=defaults["reminder_budget_max_prompts"],
        min_value=1,
        max_value=24,
    )
    reminder_budget_enforce = _coerce_bool(
        cadence_raw.get("reminder_budget_enforce"),
        defaults["reminder_budget_enforce"],
    )
    cadence_support_recovery_cooldown_hours = _coerce_int(
        cadence_raw.get("support_recovery_cooldown_hours"),
        default=defaults["cadence_support_recovery_cooldown_hours"],
        min_value=1,
        max_value=168,
    )
    cadence_override_cooldown_hours = _coerce_int(
        cadence_raw.get("override_cooldown_hours"),
        default=defaults["cadence_override_cooldown_hours"],
        min_value=1,
        max_value=168,
    )
    cadence_observe_cooldown_hours = _coerce_int(
        cadence_raw.get("observe_cooldown_hours"),
        default=defaults["cadence_observe_cooldown_hours"],
        min_value=1,
        max_value=168,
    )

    return {
        "repeated_skip": repeated_skip,
        "l2_interruption": l2_interruption,
        "stagnation_days": stagnation_days,
        "l2_protection_high": high,
        "l2_protection_medium": medium,
        "escalation_window_days": escalation_window_days,
        "escalation_firm_resistance": escalation_firm_resistance,
        "escalation_periodic_resistance": escalation_periodic_resistance,
        "safe_mode_enabled": safe_mode_enabled,
        "safe_mode_resistance_threshold": safe_mode_resistance_threshold,
        "safe_mode_min_response_events": safe_mode_min_response_events,
        "safe_mode_max_confirmation_ratio": safe_mode_max_confirmation_ratio,
        "safe_mode_recovery_confirmations": safe_mode_recovery_confirmations,
        "safe_mode_cooldown_hours": safe_mode_cooldown_hours,
        "reminder_budget_window_hours": reminder_budget_window_hours,
        "reminder_budget_max_prompts": reminder_budget_max_prompts,
        "reminder_budget_enforce": reminder_budget_enforce,
        "cadence_support_recovery_cooldown_hours": cadence_support_recovery_cooldown_hours,
        "cadence_override_cooldown_hours": cadence_override_cooldown_hours,
        "cadence_observe_cooldown_hours": cadence_observe_cooldown_hours,
    }


def _extract_task_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    event_type = event.get("type")
    if event_type in {"task_failed", "task_completed"}:
        task_id = event.get("task_id")
        return str(task_id) if task_id else None
    if event_type == "task_updated":
        payload = event.get("payload")
        if isinstance(payload, dict):
            task_id = payload.get("id")
            return str(task_id) if task_id else None
    return None


def _task_outcome_from_event(event: Dict[str, Any]) -> Optional[str]:
    event_type = event.get("type")
    if event_type == "task_completed":
        return "completed"
    if event_type == "task_failed" and event.get("failure_type") == "skipped":
        return "skipped"
    if event_type == "task_updated":
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
        status = str(updates.get("status", "")).lower()
        if status == "completed":
            return "completed"
        if status == "skipped":
            return "skipped"
    return None


def _build_l2_reference_maps() -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Build lookup maps for goal type and task->goal relations.
    Returns:
        (goal_type_by_goal_id, task_goal_by_task_id)
    """
    goal_type_by_goal_id: Dict[str, str] = {}
    task_goal_by_task_id: Dict[str, str] = {}

    try:
        from core.objective_engine.registry import GoalRegistry

        registry = GoalRegistry()
        nodes = registry.visions + registry.objectives + registry.goals
        for node in nodes:
            goal_type_by_goal_id[node.id] = str(node.goal_type or "")
    except Exception:
        pass

    try:
        state = rebuild_state()
        for task in state.get("tasks", []):
            task_id = str(getattr(task, "id", "") or "")
            goal_id = str(getattr(task, "goal_id", "") or "")
            if task_id and goal_id:
                task_goal_by_task_id[task_id] = goal_id
    except Exception:
        pass

    return goal_type_by_goal_id, task_goal_by_task_id


def _guardian_l2_protection(
    events: List[Dict[str, Any]],
    days: int,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    L2 protection ratio:
    During deep_work window, how many L2 task outcomes are protected (completed)
    vs interrupted (skipped).
    """
    goal_type_by_goal_id, task_goal_by_task_id = _build_l2_reference_maps()
    if thresholds is None:
        thresholds = _guardian_thresholds(days)
    high_threshold = _coerce_float(
        thresholds.get("l2_protection_high"),
        default=0.75,
        min_value=0.0,
        max_value=1.0,
    )
    medium_threshold = _coerce_float(
        thresholds.get("l2_protection_medium"),
        default=0.50,
        min_value=0.0,
        max_value=1.0,
    )
    if medium_threshold > high_threshold:
        medium_threshold = high_threshold

    day_keys = [
        (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in reversed(range(days))
    ]
    daily = {
        day: {"protected": 0, "interrupted": 0}
        for day in day_keys
    }

    for event in events:
        event_time = _parse_event_time(event)
        if event_time is None or _phase_for_time(event_time) != "deep_work":
            continue

        outcome = _task_outcome_from_event(event)
        if outcome not in {"completed", "skipped"}:
            continue

        task_id = _extract_task_id_from_event(event)
        if not task_id:
            continue
        goal_id = task_goal_by_task_id.get(task_id)
        if not goal_id:
            continue

        goal_type = str(goal_type_by_goal_id.get(goal_id, "")).upper()
        if "L2" not in goal_type:
            continue

        day = event_time.strftime("%Y-%m-%d")
        if day not in daily:
            continue

        if outcome == "completed":
            daily[day]["protected"] += 1
        elif outcome == "skipped":
            daily[day]["interrupted"] += 1

    points = []
    total_protected = 0
    total_interrupted = 0
    for day in day_keys:
        protected = daily[day]["protected"]
        interrupted = daily[day]["interrupted"]
        total = protected + interrupted
        ratio = round(protected / total, 2) if total > 0 else None
        points.append(
            {
                "date": day,
                "ratio": ratio,
                "protected": protected,
                "interrupted": interrupted,
            }
        )
        total_protected += protected
        total_interrupted += interrupted

    opportunities = total_protected + total_interrupted
    ratio = round(total_protected / opportunities, 2) if opportunities > 0 else None
    if ratio is None:
        level = "unknown"
        summary = "暂无可计算的 L2 保护数据。"
    elif ratio >= high_threshold:
        level = "high"
        summary = "L2 保护表现良好，深度工作时段执行稳定。"
    elif ratio >= medium_threshold:
        level = "medium"
        summary = "L2 保护一般，仍有中断，建议减少深度时段切换。"
    else:
        level = "low"
        summary = "L2 保护偏弱，深度时段中断较多，建议优先修复。"

    return {
        "ratio": ratio,
        "level": level,
        "protected": total_protected,
        "interrupted": total_interrupted,
        "opportunities": opportunities,
        "summary": summary,
        "trend": points,
        "thresholds": {"high": high_threshold, "medium": medium_threshold},
    }


def _guardian_l2_session(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    tracked_types = {
        "l2_session_started",
        "l2_session_resumed",
        "l2_session_interrupted",
        "l2_session_completed",
    }
    lifecycle_events = [ev for ev in events if ev.get("type") in tracked_types]
    if not lifecycle_events:
        return {
            "started": 0,
            "resumed": 0,
            "completed": 0,
            "interrupted": 0,
            "completion_rate": None,
            "recovery_rate": None,
            "active_session": False,
            "active_session_id": None,
            "resume_ready": False,
            "resume_session_id": None,
            "resume_reason": None,
            "resume_reason_label": None,
            "resume_hint": None,
            "micro_ritual": {
                "started_with_intention": 0,
                "completed_with_reflection": 0,
                "start_intention_rate": None,
                "completion_reflection_rate": None,
            },
            "latest": None,
            "recent_events": [],
        }

    sorted_events = sorted(
        lifecycle_events,
        key=lambda ev: _parse_event_time(ev) or datetime.min,
    )
    sessions: Dict[str, Dict[str, Any]] = {}
    started = 0
    resumed = 0
    completed = 0
    interrupted = 0
    started_with_intention = 0
    completed_with_reflection = 0

    for event in sorted_events:
        event_type = event.get("type")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            fallback = event.get("event_id") or event.get("timestamp") or str(len(sessions) + 1)
            session_id = f"l2_session_{fallback}"
        session = sessions.setdefault(session_id, {"status": "unknown", "resume_count": 0})
        session["last_activity_at"] = event.get("timestamp")

        if event_type == "l2_session_started":
            started += 1
            session["status"] = "active"
            session["started_at"] = event.get("timestamp")
            intention = str(payload.get("intention") or "").strip()
            if intention:
                started_with_intention += 1
                session["latest_intention"] = intention
        elif event_type == "l2_session_resumed":
            resumed += 1
            session["status"] = "active"
            session["resumed_at"] = event.get("timestamp")
            session["resume_count"] = int(session.get("resume_count") or 0) + 1
            resume_step = str(payload.get("resume_step") or "").strip()
            if resume_step:
                session["latest_resume_step"] = resume_step
        elif event_type == "l2_session_interrupted":
            interrupted += 1
            session["status"] = "interrupted"
            session["interrupted_at"] = event.get("timestamp")
            session["interrupt_reason"] = payload.get("reason")
        elif event_type == "l2_session_completed":
            completed += 1
            session["status"] = "completed"
            session["completed_at"] = event.get("timestamp")
            reflection = str(payload.get("reflection") or "").strip()
            if reflection:
                completed_with_reflection += 1
                session["latest_reflection"] = reflection

    terminal = completed + interrupted
    completion_rate = round(completed / terminal, 2) if terminal > 0 else None
    recovery_rate = round(resumed / interrupted, 2) if interrupted > 0 else None

    active_session_id = None
    active_candidates = []
    for sid, session in sessions.items():
        if session.get("status") != "active":
            continue
        parsed = _parse_event_time({"timestamp": session.get("last_activity_at")}) or datetime.min
        active_candidates.append((sid, parsed))
    if active_candidates:
        active_session_id = sorted(active_candidates, key=lambda item: item[1])[-1][0]

    resume_session_id = None
    interrupted_candidates = []
    for sid, session in sessions.items():
        if session.get("status") != "interrupted":
            continue
        parsed = _parse_event_time({"timestamp": session.get("interrupted_at")}) or datetime.min
        interrupted_candidates.append((sid, parsed))
    if interrupted_candidates:
        resume_session_id = sorted(interrupted_candidates, key=lambda item: item[1])[-1][0]

    resume_reason = None
    resume_reason_label = None
    resume_hint = None
    if resume_session_id:
        session = sessions.get(resume_session_id, {})
        resume_reason = str(session.get("interrupt_reason") or "").strip() or None
        if resume_reason:
            resume_reason_label = L2_SESSION_INTERRUPT_REASON_LABELS.get(
                resume_reason,
                resume_reason,
            )
            resume_hint = L2_SESSION_RESUME_HINTS.get(
                resume_reason,
                L2_SESSION_RESUME_HINTS["other"],
            )

    latest = sorted_events[-1] if sorted_events else None
    latest_payload = (
        latest.get("payload")
        if isinstance(latest and latest.get("payload"), dict)
        else {}
    )
    latest_reason = latest_payload.get("reason") if isinstance(latest_payload, dict) else None
    latest_reason_label = (
        L2_SESSION_INTERRUPT_REASON_LABELS.get(str(latest_reason), str(latest_reason))
        if latest_reason
        else None
    )

    recent_events: List[Dict[str, Any]] = []
    for ev in sorted_events[-5:]:
        ev_type = ev.get("type")
        ev_payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        if ev_type == "l2_session_interrupted":
            reason = str(ev_payload.get("reason") or "other")
            reason_label = L2_SESSION_INTERRUPT_REASON_LABELS.get(reason, reason)
            detail = f"session interrupted ({reason_label})"
        elif ev_type == "l2_session_resumed":
            if str(ev_payload.get("resume_step") or "").strip():
                detail = "session resumed (minimal step captured)"
            else:
                detail = "session resumed"
        elif ev_type == "l2_session_completed":
            if str(ev_payload.get("reflection") or "").strip():
                detail = "session completed (reflection captured)"
            else:
                detail = "session completed"
        else:
            if str(ev_payload.get("intention") or "").strip():
                detail = "session started (intention captured)"
            else:
                detail = "session started"
        recent_events.append(_event_evidence(ev, detail))

    latest_snapshot = None
    if latest:
        latest_snapshot = {
            "type": latest.get("type"),
            "timestamp": latest.get("timestamp"),
            "session_id": (
                latest_payload.get("session_id")
                if isinstance(latest_payload, dict)
                else None
            ),
            "reason": latest_reason,
            "reason_label": latest_reason_label,
        }

    return {
        "started": started,
        "resumed": resumed,
        "completed": completed,
        "interrupted": interrupted,
        "completion_rate": completion_rate,
        "recovery_rate": recovery_rate,
        "active_session": bool(active_session_id),
        "active_session_id": active_session_id,
        "resume_ready": bool(resume_session_id),
        "resume_session_id": resume_session_id,
        "resume_reason": resume_reason,
        "resume_reason_label": resume_reason_label,
        "resume_hint": resume_hint,
        "micro_ritual": {
            "started_with_intention": started_with_intention,
            "completed_with_reflection": completed_with_reflection,
            "start_intention_rate": (
                round(started_with_intention / started, 2) if started > 0 else None
            ),
            "completion_reflection_rate": (
                round(completed_with_reflection / completed, 2) if completed > 0 else None
            ),
        },
        "latest": latest_snapshot,
        "recent_events": recent_events,
    }


def _detect_deviation_signals(
    events: List[Dict[str, Any]],
    days: int,
    thresholds: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Detect behavior deviation signals and provide traceable evidence.
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
        thresholds = _guardian_thresholds(days)

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

    return signals


def _l2_interruption_evidence(
    events: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
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


def generate_report(days: int = 7) -> Dict[str, Any]:
    """
    Generate a comprehensive retrospective report.

    Args:
        days: Period to analyze (default: 7 days)

    Returns:
        Report dictionary with all analytics.
    """
    events = load_events_for_period(days)

    report = {
        "period": {
            "days": days,
            "start_date": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d")
        },
        "generated_at": datetime.now().isoformat(),
        "statistics": analyze_completion_stats(events),
        "failure_patterns": identify_failure_patterns(events),
        "activity_trend": calculate_activity_trend(events),
        "event_count": len(events)
    }

    return report


def generate_ai_insights(report: Dict[str, Any]) -> str:
    """
    Use LLM to generate human-readable insights from the report.

    Args:
        report: The analysis report.

    Returns:
        AI-generated insights text.
    """
    llm = get_llm("long_memory")

    if llm.get_model_name() == "rule_based":
        # 规则模式：生成简单摘要
        stats = report.get("statistics", {})
        return f"""本周执行报告摘要：
- 总任务数: {stats.get('total_tasks', 0)}
- 完成率: {stats.get('completion_rate', 0) * 100:.0f}%
- 跳过任务: {stats.get('skipped', 0)}
- 受阻任务: {stats.get('blocked', 0)}

建议：关注失败模式，调整任务策略。"""

    # LLM 模式：生成详细洞察
    prompt = f"""分析以下 AI Life OS 执行报告，生成简洁的改进建议：

{json.dumps(report, ensure_ascii=False, indent=2)}

要求：
1. 用 2-3 句话总结本周执行情况
2. 识别最大的瓶颈
3. 给出 1-2 个具体可行的改进建议
"""

    system_prompt = """你是 AI Life OS 的复盘助手。
分析用户的执行数据，给出客观、可行的改进建议。
保持简洁，避免空洞的建议。"""

    response = llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.5,
        max_tokens=500
    )

    if response.success:
        return response.content
    else:
        return f"无法生成 AI 洞察：{response.error}"


def weekly_retrospective() -> Dict[str, Any]:
    """
    Generate a complete weekly retrospective with AI insights.

    Returns:
        Full retrospective report with insights.
    """
    report = generate_report(days=7)
    report["ai_insights"] = generate_ai_insights(report)
    return report


# --- GuardianRetrospective (derived view, read-only from event_log) ---

def _guardian_rhythm(events: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    """执行节奏：节律是否断裂、一句话摘要。数据来源：事件时间分布。"""
    daily = calculate_activity_trend(events)
    if not daily:
        return {"broken": False, "summary": "本周期无执行记录。"}
    start = datetime.now().date() - timedelta(days=days)
    expected_dates = [
        (start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days + 1)
    ]
    active_dates = set(d for d in expected_dates if daily.get(d, 0) > 0)
    gaps = 0
    for i, d in enumerate(expected_dates[:-1]):
        if d in active_dates and expected_dates[i + 1] not in active_dates:
            gaps += 1
    broken = gaps >= 2
    summary = "本周期执行节奏连续。" if not broken else "本周期内存在多日无执行记录，节律可能断裂。"
    return {"broken": broken, "summary": summary}


def _guardian_alignment(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """目标一致性：是否偏离 Vision/Objective。数据来源：事件 goal_id + GoalRegistry 树。"""
    registry = None
    try:
        from core.objective_engine.registry import GoalRegistry
        from core.objective_engine.models import GoalLayer
        registry = GoalRegistry()
    except Exception:
        pass
    goal_ids_from_events = set()
    for ev in events:
        if ev.get("type") in (
            "goal_confirmed",
            "goal_rejected",
            "goal_completed",
            "goal_feedback",
            "goal_action",
        ):
            goal_ids_from_events.add(ev.get("goal_id", ""))
    if not registry or not goal_ids_from_events:
        return {"deviated": False, "summary": "暂无目标层级数据或相关事件。"}
    def under_vision_or_objective(goal_id: str) -> bool:
        node = registry.get_node(goal_id)
        if not node:
            return False
        cur = node
        while cur:
            if cur.layer == GoalLayer.VISION or cur.layer == GoalLayer.OBJECTIVE:
                return True
            if not cur.parent_id:
                break
            cur = registry.get_node(cur.parent_id)
        return False
    linked = sum(1 for gid in goal_ids_from_events if gid and under_vision_or_objective(gid))
    rejected = sum(1 for ev in events if ev.get("type") == "goal_rejected")
    completed = sum(1 for ev in events if ev.get("type") == "goal_completed")
    deviated = rejected > 0 or (linked > 0 and completed < linked)
    summary = (
        "执行与愿景/目标方向一致。"
        if not deviated
        else "存在拒绝或未完成与愿景相关的目标，可回顾当前重心。"
    )
    return {"deviated": deviated, "summary": summary}


def _goal_alignment_trend(events: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    """
    Build a weekly trend view for goal-anchor alignment.
    """
    try:
        from core.objective_engine.registry import GoalRegistry

        registry = GoalRegistry()
        nodes = registry.visions + registry.objectives + registry.goals
        score_by_goal_id = {
            node.id: float(node.alignment_score)
            for node in nodes
            if isinstance(node.alignment_score, (int, float))
        }
        anchor_versions = [
            node.anchor_version for node in nodes if getattr(node, "anchor_version", None)
        ]
    except Exception:
        score_by_goal_id = {}
        anchor_versions = []

    day_keys = [
        (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in reversed(range(days))
    ]
    daily_samples: Dict[str, List[float]] = {key: [] for key in day_keys}

    tracked_event_types = {
        "goal_action",
        "goal_feedback",
        "goal_completed",
        "goal_registry_created",
        "goal_registry_updated",
        "goal_registry_confirmed",
    }
    seen = set()
    for event in events:
        event_type = event.get("type")
        if event_type not in tracked_event_types:
            continue
        event_time = _parse_event_time(event)
        if event_time is None:
            continue
        day = event_time.strftime("%Y-%m-%d")
        if day not in daily_samples:
            continue

        goal_id = str(event.get("goal_id") or "")
        score = score_by_goal_id.get(goal_id)
        if score is None:
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            node = payload.get("node") if isinstance(payload.get("node"), dict) else {}
            raw_score = node.get("alignment_score")
            if isinstance(raw_score, (int, float)):
                score = float(raw_score)
        if score is None:
            continue

        dedupe_key = (event.get("event_id"), day, goal_id, score)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        daily_samples[day].append(score)

    points = []
    valid_points = []
    for day in day_keys:
        samples = daily_samples[day]
        avg_score = round(sum(samples) / len(samples), 1) if samples else None
        point = {"date": day, "avg_score": avg_score, "samples": len(samples)}
        points.append(point)
        if avg_score is not None:
            valid_points.append(point)

    if len(valid_points) < 2:
        trend_summary = "暂无可计算的目标对齐趋势。"
    else:
        delta = valid_points[-1]["avg_score"] - valid_points[0]["avg_score"]
        if delta >= 8:
            trend_summary = "目标对齐趋势在改善。"
        elif delta <= -8:
            trend_summary = "目标对齐趋势在下降，建议复核近期目标。"
        else:
            trend_summary = "目标对齐趋势整体稳定。"

    return {
        "available": bool(valid_points),
        "summary": trend_summary,
        "points": points,
        "active_anchor_version": anchor_versions[-1] if anchor_versions else None,
    }


def _guardian_friction(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """行为摩擦点：反复 skip、延迟信号。数据来源：task_updated (SKIPPED)、failure 信号。"""
    skip_count = 0
    for ev in events:
        if ev.get("type") == "task_updated":
            payload = ev.get("payload") or {}
            if payload.get("updates", {}).get("status") == "skipped":
                skip_count += 1
        if ev.get("type") == "task_failed" and ev.get("failure_type") == "skipped":
            skip_count += 1
    repeated_skip = skip_count >= 2
    delay_signals = False
    if repeated_skip:
        summary = "存在多次跳过任务，建议拆分为更小步骤或调整优先级。"
    elif skip_count == 1:
        summary = "本周期有一次跳过，属正常调整。"
    else:
        summary = "无明显行为摩擦。"
    return {"repeated_skip": repeated_skip, "delay_signals": delay_signals, "summary": summary}


def _guardian_observations(
    rhythm: Dict[str, Any],
    alignment: Dict[str, Any],
    friction: Dict[str, Any],
    l2_protection: Optional[Dict[str, Any]] = None,
    deviation_signals: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """1–3 条 Guardian 观察，由三维度派生，不硬编码固定文案。"""
    out = []
    if rhythm.get("broken"):
        out.append(rhythm.get("summary", "本周期内存在多日无执行记录，节律可能断裂。"))
    if alignment.get("deviated"):
        out.append(
            alignment.get(
                "summary",
                "部分与愿景相关的目标被跳过或拒绝，可回顾是否与当前重心一致。",
            )
        )
    if friction.get("repeated_skip"):
        out.append(friction.get("summary", "存在多次跳过任务，建议拆分为更小步骤或调整优先级。"))
    if l2_protection:
        if l2_protection.get("level") in {"low", "medium"}:
            out.append(l2_protection.get("summary", "L2 保护需要提升。"))
    if deviation_signals:
        active_signal_summaries = [
            s.get("summary")
            for s in deviation_signals
            if s.get("active") and s.get("summary")
        ]
        out.extend(active_signal_summaries[:2])
    if not out:
        out.append("本周期执行平稳，无异常信号。")
    return out[:3]


def generate_guardian_retrospective(days: int = 7) -> Dict[str, Any]:
    """
    Guardian 复盘：派生视图，只读 event_log，不写入。
    输出契约见 .taskflow/active/next-version-plan/design.md §1.2。
    """
    events = load_events_for_period(days)
    now = datetime.now()
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    thresholds = _guardian_thresholds(days)

    rhythm = _guardian_rhythm(events, days)
    alignment = _guardian_alignment(events)
    alignment["trend"] = _goal_alignment_trend(events, days)
    friction = _guardian_friction(events)
    l2_protection = _guardian_l2_protection(events, days, thresholds=thresholds)
    l2_session = _guardian_l2_session(events)
    deviation_signals = _detect_deviation_signals(events, days, thresholds=thresholds)
    observations = _guardian_observations(
        rhythm,
        alignment,
        friction,
        l2_protection,
        deviation_signals,
    )

    return {
        "period": {"days": days, "start_date": start_date, "end_date": end_date},
        "generated_at": now.isoformat(),
        "rhythm": rhythm,
        "alignment": alignment,
        "friction": friction,
        "l2_protection": l2_protection,
        "l2_session": l2_session,
        "deviation_signals": deviation_signals,
        "observations": observations,
    }


def get_intervention_level() -> str:
    """从 config/blueprint.yaml 读取 intervention_level：OBSERVE_ONLY | SOFT | ASK。默认 SOFT。"""
    data = _load_blueprint_config()
    level = data.get("intervention_level", "SOFT")
    if level in ("OBSERVE_ONLY", "SOFT", "ASK"):
        return level
    return "SOFT"


def _build_confirmation_fingerprint(raw: Dict[str, Any]) -> str:
    """
    Build a stable fingerprint for current intervention context.
    Used to make ASK confirmations replayable and idempotent.
    """
    active_signals = []
    for signal in raw.get("deviation_signals", []):
        if not signal.get("active"):
            continue
        active_signals.append(
            {
                "name": signal.get("name"),
                "severity": signal.get("severity"),
                "count": signal.get("count", 0),
                "threshold": signal.get("threshold"),
            }
        )

    payload = {
        "days": (raw.get("period") or {}).get("days"),
        "suggestion": (raw.get("observations") or [""])[0] if raw.get("observations") else "",
        "signals": active_signals,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"gcf_{hashlib.sha256(encoded).hexdigest()[:16]}"


def _normalize_guardian_response_context(raw_context: Any) -> Optional[str]:
    context = str(raw_context or "").strip().lower()
    if not context:
        return None
    if context in GUARDIAN_RESPONSE_CONTEXTS:
        return context
    return None


def _guardian_context_options() -> List[Dict[str, str]]:
    return [
        {
            "value": context,
            "label": GUARDIAN_RESPONSE_CONTEXT_LABELS.get(context, context),
            "description": GUARDIAN_RESPONSE_CONTEXT_HINTS.get(context, ""),
        }
        for context in GUARDIAN_RESPONSE_CONTEXTS
    ]


def _l2_session_interrupt_reason_options() -> List[Dict[str, str]]:
    return [
        {"value": key, "label": value}
        for key, value in L2_SESSION_INTERRUPT_REASON_LABELS.items()
    ]


def _narrative_event_detail(event: Dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")
    if event_type == "progress_updated":
        return "progress logged"
    if event_type == "guardian_intervention_confirmed":
        return "guardian suggestion confirmed"
    if event_type == "goal_alignment_recomputed":
        return "goal alignment recomputed"
    if event_type == "l2_session_completed":
        return "L2 session completed"
    if event_type == "l2_session_resumed":
        return "L2 session resumed"
    if event_type == "execution_completed":
        return "execution completed"
    if event_type == "anchor_activated":
        return "anchor activated"
    if event_type == "guardian_intervention_responded":
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        action = str(payload.get("action") or "").strip().lower()
        context = str(payload.get("context") or "").strip().lower()
        if action and context:
            return f"guardian response recorded ({action}, {context})"
        if action:
            return f"guardian response recorded ({action})"
        return "guardian response recorded"
    if event_type == "task_updated":
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
        status = str(updates.get("status") or "").strip().lower()
        if status == "completed":
            return "task completed"
        if status == "skipped":
            return "task skipped"
    return event_type.replace("_", " ").strip() or "event recorded"


def _recent_narrative_evidence(
    events: List[Dict[str, Any]],
    *,
    include_types: Optional[set] = None,
    include_completed_task_updates: bool = False,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    include_types = include_types or set()
    for event in events:
        event_type = str(event.get("type") or "")
        if event_type in include_types:
            matched.append(event)
            continue
        if include_completed_task_updates and event_type == "task_updated":
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
            if str(updates.get("status") or "").strip().lower() == "completed":
                matched.append(event)

    sorted_events = sorted(
        matched,
        key=lambda ev: _parse_event_time(ev) or datetime.min,
    )
    recent = sorted_events[-limit:]
    return [_event_evidence(ev, _narrative_event_detail(ev)) for ev in recent]


def _next_week_behavior_focus(
    *,
    deviation_signals: List[Dict[str, Any]],
    north_star_metrics: Dict[str, Any],
    l2_session: Dict[str, Any],
) -> Dict[str, str]:
    signals = deviation_signals if isinstance(deviation_signals, list) else []
    repeated_skip_signal = next(
        (s for s in signals if str(s.get("name") or "") == "repeated_skip"),
        {},
    )
    l2_interrupt_signal = next(
        (s for s in signals if str(s.get("name") or "") == "l2_interruption"),
        {},
    )

    mundane_rate = None
    mundane_payload = (
        north_star_metrics.get("mundane_automation_coverage")
        if isinstance(north_star_metrics.get("mundane_automation_coverage"), dict)
        else {}
    )
    if isinstance(mundane_payload, dict) and isinstance(mundane_payload.get("rate"), (int, float)):
        mundane_rate = float(mundane_payload["rate"])

    if (
        isinstance(l2_interrupt_signal, dict)
        and l2_interrupt_signal.get("active")
    ) or bool(l2_session.get("resume_ready")):
        reinforce = (
            "When interrupted, resume the same L2 session "
            "with one minimal next step in 10 minutes."
        )
    elif isinstance(mundane_rate, (int, float)) and mundane_rate < 0.55:
        reinforce = "Apply L1 recovery batch daily to keep mundane tasks outsourced."
    else:
        reinforce = (
            "Start each L2 block with one intention sentence "
            "and close it with one reflection sentence."
        )

    if isinstance(repeated_skip_signal, dict) and repeated_skip_signal.get("active"):
        reduce = (
            "Reduce repeated skipping by splitting oversized tasks "
            "before the next execution block."
        )
    elif isinstance(l2_interrupt_signal, dict) and l2_interrupt_signal.get("active"):
        reduce = "Reduce context switching during L2 blocks."
    else:
        reduce = "Reduce reactive context hopping during planned focus windows."

    return {"reinforce": reinforce, "reduce": reduce}


def _blueprint_narrative_loop(
    *,
    events: List[Dict[str, Any]],
    deviation_signals: List[Dict[str, Any]],
    north_star_metrics: Dict[str, Any],
    l2_session: Dict[str, Any],
    alignment: Dict[str, Any],
) -> Dict[str, Any]:
    wisdom_evidence = _recent_narrative_evidence(
        events,
        include_types={
            "progress_updated",
            "guardian_intervention_confirmed",
            "goal_alignment_recomputed",
        },
        include_completed_task_updates=False,
    )
    experience_evidence = _recent_narrative_evidence(
        events,
        include_types={
            "l2_session_completed",
            "l2_session_resumed",
            "execution_completed",
        },
        include_completed_task_updates=True,
    )
    connection_evidence = _recent_narrative_evidence(
        events,
        include_types={
            "anchor_activated",
            "guardian_intervention_responded",
            "goal_alignment_recomputed",
        },
        include_completed_task_updates=False,
    )

    alignment_delta_payload = (
        north_star_metrics.get("alignment_delta_weekly")
        if isinstance(north_star_metrics.get("alignment_delta_weekly"), dict)
        else {}
    )
    alignment_delta = (
        float(alignment_delta_payload.get("delta"))
        if isinstance(alignment_delta_payload.get("delta"), (int, float))
        else None
    )

    l2_completion_rate = (
        float(l2_session.get("completion_rate"))
        if isinstance(l2_session.get("completion_rate"), (int, float))
        else None
    )
    l2_recovery_rate = (
        float(l2_session.get("recovery_rate"))
        if isinstance(l2_session.get("recovery_rate"), (int, float))
        else None
    )

    wisdom_progress = bool(wisdom_evidence) or (
        isinstance(alignment_delta, (int, float)) and alignment_delta > 0
    )
    experience_progress = bool(experience_evidence) or (
        isinstance(l2_completion_rate, (int, float)) and l2_completion_rate >= 0.5
    )
    connection_progress = bool(connection_evidence)

    focus = _next_week_behavior_focus(
        deviation_signals=deviation_signals,
        north_star_metrics=north_star_metrics,
        l2_session=l2_session,
    )

    if wisdom_progress and experience_progress and connection_progress:
        summary = (
            "This week shows balanced progress across cognition, "
            "lived execution, and value connection."
        )
    elif sum([wisdom_progress, experience_progress, connection_progress]) >= 2:
        summary = (
            "This week made partial progress; strengthen the weakest dimension next week."
        )
    else:
        summary = (
            "Progress evidence is still sparse; keep actions smaller and more traceable next week."
        )

    alignment_trend_summary = (
        str((alignment.get("trend") or {}).get("summary") or "").strip()
        if isinstance(alignment, dict)
        else ""
    )

    return {
        "dimensions": {
            "wisdom": {
                "progress": wisdom_progress,
                "summary": (
                    "Cognitive progress is visible via reflection/alignment evidence."
                    if wisdom_progress
                    else "Cognitive progress evidence is limited this cycle."
                ),
                "evidence": wisdom_evidence,
            },
            "experience": {
                "progress": experience_progress,
                "summary": (
                    "Execution experience improved through completed/resumed focus work."
                    if experience_progress
                    else "Execution experience evidence is limited this cycle."
                ),
                "evidence": experience_evidence,
            },
            "connection": {
                "progress": connection_progress,
                "summary": (
                    "Choices remained connected to blueprint and guardian context."
                    if connection_progress
                    else "Connection to blueprint evidence is limited this cycle."
                ),
                "evidence": connection_evidence,
            },
        },
        "narrative_card": {
            "title": "How This Week Served Long-Term Value",
            "summary": summary,
            "alignment_trend": alignment_trend_summary,
            "reinforce_behavior": focus["reinforce"],
            "reduce_behavior": focus["reduce"],
            "l2_recovery_rate": l2_recovery_rate,
            "l2_completion_rate": l2_completion_rate,
        },
    }


def _guardian_role_for_context(context: Optional[str] = None) -> Dict[str, Any]:
    normalized_context = _normalize_guardian_response_context(context)
    role = {
        "representing": "BLUEPRINT_SELF",
        "representing_label": "价值自我",
        "facing": "INSTINCT_SELF",
        "facing_label": "本能自我",
        "mode": "overrule_instincts",
        "message": "系统正在代表价值自我，优先保护长期目标。",
        "context": normalized_context,
        "context_label": (
            GUARDIAN_RESPONSE_CONTEXT_LABELS.get(normalized_context)
            if normalized_context
            else None
        ),
    }
    if normalized_context == "recovering":
        role.update(
            {
                "facing": "REFLECTIVE_SELF",
                "facing_label": "反思自我",
                "mode": "support_recovery",
                "message": "系统正在代表价值自我，支持你恢复后继续推进。",
            }
        )
    elif normalized_context == "resource_blocked":
        role.update(
            {
                "facing": "REFLECTIVE_SELF",
                "facing_label": "反思自我",
                "mode": "remove_blockers",
                "message": "系统正在代表价值自我，优先协助清理执行阻塞。",
            }
        )
    elif normalized_context == "task_too_big":
        role.update(
            {
                "facing": "REFLECTIVE_SELF",
                "facing_label": "反思自我",
                "mode": "reduce_task_granularity",
                "message": "系统正在代表价值自我，把目标拆到可立即执行的最小步骤。",
            }
        )
    elif normalized_context == "instinct_escape":
        role.update(
            {
                "facing": "INSTINCT_SELF",
                "facing_label": "本能自我",
                "mode": "overrule_instincts",
                "message": "检测到可能的本能逃避，系统将温和但坚定地代表价值自我干预。",
            }
        )
    return role


def _guardian_response_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event_type = event.get("type")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    context = _normalize_guardian_response_context(payload.get("context"))
    if event_type == "guardian_intervention_confirmed":
        return {
            "action": "confirm",
            "context": context,
            "event": event,
            "payload": payload,
            "timestamp": event.get("timestamp"),
            "parsed_time": _parse_event_time(event),
        }
    if event_type != "guardian_intervention_responded":
        return None
    action = str(payload.get("action", "")).lower()
    if action not in GUARDIAN_RESPONSE_ACTIONS:
        return None
    return {
        "action": action,
        "context": context,
        "event": event,
        "payload": payload,
        "timestamp": event.get("timestamp"),
        "parsed_time": _parse_event_time(event),
    }


def _iter_guardian_response_events(
    events: List[Dict[str, Any]],
    days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for event in events:
        normalized = _guardian_response_from_event(event)
        if not normalized:
            continue
        payload = normalized["payload"] if isinstance(normalized["payload"], dict) else {}
        payload_days = payload.get("days")
        if days is not None and payload_days is not None:
            try:
                if int(payload_days) != int(days):
                    continue
            except (TypeError, ValueError):
                continue
        normalized["fingerprint"] = payload.get("fingerprint")
        normalized["note"] = payload.get("note", "")
        normalized["recovery_step"] = payload.get("recovery_step")
        normalized["context"] = normalized.get("context")
        normalized["context_label"] = (
            GUARDIAN_RESPONSE_CONTEXT_LABELS.get(normalized.get("context"))
            if normalized.get("context")
            else None
        )
        out.append(normalized)
    return out


def _find_guardian_response_event(
    events: List[Dict[str, Any]],
    days: int,
    fingerprint: Optional[str],
    action: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    for normalized in reversed(_iter_guardian_response_events(events, days=days)):
        if action and normalized.get("action") != action:
            continue
        if fingerprint and normalized.get("fingerprint") != fingerprint:
            continue
        return normalized
    return None


def _safe_mode_state_from_runtime() -> Dict[str, Any]:
    try:
        state = rebuild_state()
    except Exception:
        state = {}
    guardian = state.get("guardian") if isinstance(state, dict) else {}
    guardian = guardian if isinstance(guardian, dict) else {}
    safe_mode = guardian.get("safe_mode")
    if not isinstance(safe_mode, dict):
        safe_mode = {}
    return {
        "active": bool(safe_mode.get("active", False)),
        "entered_at": safe_mode.get("entered_at"),
        "exited_at": safe_mode.get("exited_at"),
        "reason": safe_mode.get("reason"),
    }


def _guardian_authority_snapshot(
    events: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    window_days = _coerce_int(
        thresholds.get("escalation_window_days"),
        default=7,
        min_value=1,
        max_value=30,
    )
    firm_threshold = _coerce_int(
        thresholds.get("escalation_firm_resistance"),
        default=2,
        min_value=1,
        max_value=99,
    )
    periodic_threshold = _coerce_int(
        thresholds.get("escalation_periodic_resistance"),
        default=4,
        min_value=1,
        max_value=99,
    )
    if periodic_threshold < firm_threshold:
        periodic_threshold = firm_threshold

    responses = _iter_guardian_response_events(events)
    window_start = now - timedelta(days=window_days)
    window_responses = [
        entry
        for entry in responses
        if entry.get("parsed_time") and entry["parsed_time"] >= window_start
    ]
    response_count = len(window_responses)
    resistance_count = sum(
        1 for entry in window_responses if entry.get("action") in {"dismiss", "snooze"}
    )
    confirmation_count = sum(1 for entry in window_responses if entry.get("action") == "confirm")
    confirmation_ratio = (
        round(confirmation_count / response_count, 2) if response_count > 0 else None
    )

    if resistance_count >= periodic_threshold:
        stage = "periodic_check"
    elif resistance_count >= firm_threshold:
        stage = "firm_reminder"
    else:
        stage = "gentle_nudge"

    safe_mode_enabled = _coerce_bool(thresholds.get("safe_mode_enabled"), True)
    safe_mode_resistance_threshold = _coerce_int(
        thresholds.get("safe_mode_resistance_threshold"),
        default=5,
        min_value=1,
        max_value=999,
    )
    safe_mode_min_events = _coerce_int(
        thresholds.get("safe_mode_min_response_events"),
        default=3,
        min_value=1,
        max_value=999,
    )
    safe_mode_max_ratio = _coerce_float(
        thresholds.get("safe_mode_max_confirmation_ratio"),
        default=0.34,
        min_value=0.0,
        max_value=1.0,
    )
    safe_mode_recovery_confirmations = _coerce_int(
        thresholds.get("safe_mode_recovery_confirmations"),
        default=2,
        min_value=1,
        max_value=999,
    )
    safe_mode_cooldown_hours = _coerce_int(
        thresholds.get("safe_mode_cooldown_hours"),
        default=24,
        min_value=1,
        max_value=720,
    )

    safe_mode_state = _safe_mode_state_from_runtime()
    safe_mode_active = bool(safe_mode_state.get("active"))
    entered_at_raw = safe_mode_state.get("entered_at")
    entered_at = None
    if isinstance(entered_at_raw, str):
        try:
            entered_at = datetime.fromisoformat(entered_at_raw.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            entered_at = None

    confirmations_since_enter = 0
    for entry in responses:
        if entry.get("action") != "confirm":
            continue
        parsed_time = entry.get("parsed_time")
        if not parsed_time:
            continue
        if entered_at and parsed_time < entered_at:
            continue
        confirmations_since_enter += 1

    if entered_at:
        cooldown_ends_at = entered_at + timedelta(hours=safe_mode_cooldown_hours)
        cooldown_complete = now >= cooldown_ends_at
        cooldown_ends_at_str = cooldown_ends_at.isoformat()
    else:
        cooldown_complete = True
        cooldown_ends_at_str = None

    should_enter_safe_mode = (
        safe_mode_enabled
        and not safe_mode_active
        and response_count >= safe_mode_min_events
        and resistance_count >= safe_mode_resistance_threshold
        and confirmation_ratio is not None
        and confirmation_ratio <= safe_mode_max_ratio
    )
    should_exit_safe_mode = (
        safe_mode_active
        and (
            (not safe_mode_enabled)
            or (
                cooldown_complete
                and confirmations_since_enter >= safe_mode_recovery_confirmations
            )
        )
    )

    recommendation_reason = ""
    if should_enter_safe_mode:
        recommendation_reason = "high_resistance_low_follow_through"
    elif should_exit_safe_mode and not safe_mode_enabled:
        recommendation_reason = "disabled_in_config"
    elif should_exit_safe_mode:
        recommendation_reason = "recovery_confirmation_threshold_met"

    return {
        "escalation": {
            "stage": stage,
            "window_days": window_days,
            "response_count": response_count,
            "resistance_count": resistance_count,
            "confirmation_count": confirmation_count,
            "confirmation_ratio": confirmation_ratio,
            "firm_reminder_resistance": firm_threshold,
            "periodic_check_resistance": periodic_threshold,
        },
        "safe_mode": {
            "enabled": safe_mode_enabled,
            "active": safe_mode_active,
            "entered_at": safe_mode_state.get("entered_at"),
            "exited_at": safe_mode_state.get("exited_at"),
            "reason": safe_mode_state.get("reason"),
            "cooldown_hours": safe_mode_cooldown_hours,
            "cooldown_complete": cooldown_complete,
            "cooldown_ends_at": cooldown_ends_at_str,
            "recommendation": {
                "should_enter": should_enter_safe_mode,
                "should_exit": should_exit_safe_mode,
                "reason": recommendation_reason,
                "response_count": response_count,
                "resistance_count": resistance_count,
                "confirmation_ratio": confirmation_ratio,
                "confirmations_since_enter": confirmations_since_enter,
                "resistance_threshold": safe_mode_resistance_threshold,
                "min_response_events": safe_mode_min_events,
                "max_confirmation_ratio": safe_mode_max_ratio,
                "recovery_confirmations": safe_mode_recovery_confirmations,
            },
        },
    }


def _find_confirmation_event(
    events: List[Dict[str, Any]],
    days: int,
    fingerprint: str,
) -> Optional[Dict[str, Any]]:
    """
    Find the latest matching ASK confirmation event in current lookback window.
    """
    normalized = _find_guardian_response_event(
        events=events,
        days=days,
        fingerprint=fingerprint,
        action="confirm",
    )
    return normalized["event"] if normalized else None


def _guardian_humanization_metrics(
    *,
    events: List[Dict[str, Any]],
    days: int,
    deviation_signals: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    recovery_suggestions: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "task_recovery_suggested":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        recovery_task_id = str(payload.get("recovery_task_id") or "").strip()
        if recovery_task_id:
            recovery_suggestions[recovery_task_id] = event

    adopted_recovery_ids = set()
    for event in events:
        if _task_outcome_from_event(event) != "completed":
            continue
        task_id = _extract_task_id_from_event(event)
        if task_id and task_id in recovery_suggestions:
            adopted_recovery_ids.add(task_id)

    recovery_suggested = len(recovery_suggestions)
    recovery_adopted = len(adopted_recovery_ids)
    recovery_pending = max(0, recovery_suggested - recovery_adopted)
    recovery_rate = (
        round(recovery_adopted / recovery_suggested, 2)
        if recovery_suggested > 0
        else None
    )
    if recovery_rate is None:
        recovery_level = "unknown"
        recovery_summary = "No recovery suggestions were created in this period."
    elif recovery_rate >= 0.75:
        recovery_level = "high"
        recovery_summary = "Recovery suggestions were adopted consistently."
    elif recovery_rate >= 0.40:
        recovery_level = "medium"
        recovery_summary = "Recovery suggestions are partially adopted."
    else:
        recovery_level = "low"
        recovery_summary = "Recovery suggestions are often left pending."

    signal_by_name: Dict[str, Dict[str, Any]] = {}
    for signal in deviation_signals or []:
        if not isinstance(signal, dict):
            continue
        name = str(signal.get("name") or "").strip()
        if name:
            signal_by_name[name] = signal

    def _signal_count_threshold(
        name: str,
        default_threshold: int,
    ) -> Tuple[int, int]:
        signal = signal_by_name.get(name) or {}
        count = _coerce_int(signal.get("count"), default=0, min_value=0, max_value=9999)
        threshold = _coerce_int(
            signal.get("threshold"),
            default=default_threshold,
            min_value=1,
            max_value=9999,
        )
        return count, threshold

    repeated_skip_count, repeated_skip_threshold = _signal_count_threshold(
        "repeated_skip",
        2,
    )
    l2_interrupt_count, l2_interrupt_threshold = _signal_count_threshold(
        "l2_interruption",
        1,
    )
    stagnation_days, stagnation_threshold = _signal_count_threshold(
        "stagnation",
        (3 if days >= 3 else 1),
    )

    repeated_skip_load = min(repeated_skip_count / repeated_skip_threshold, 1.0)
    l2_interrupt_load = min(l2_interrupt_count / l2_interrupt_threshold, 1.0)
    stagnation_load = min(stagnation_days / stagnation_threshold, 1.0)
    friction_score = round(
        (repeated_skip_load + l2_interrupt_load + stagnation_load) / 3,
        2,
    )
    if friction_score >= 0.67:
        friction_level = "high"
        friction_summary = "Execution friction is high and likely visible to the user."
    elif friction_score >= 0.34:
        friction_level = "medium"
        friction_summary = "Execution friction exists and should be reduced proactively."
    else:
        friction_level = "low"
        friction_summary = "Execution friction is currently manageable."

    support_contexts = {"recovering", "resource_blocked", "task_too_big"}
    support_count = 0
    override_count = 0
    response_entries = _iter_guardian_response_events(events, days=days)
    for entry in response_entries:
        context = _normalize_guardian_response_context(entry.get("context"))
        action = str(entry.get("action") or "").strip().lower()

        if context in support_contexts:
            support_count += 1
            continue
        if context == "instinct_escape":
            override_count += 1
            continue

        if action == "dismiss":
            override_count += 1
        elif action in {"confirm", "snooze"}:
            support_count += 1

    support_total = support_count + override_count
    support_ratio = (
        round(support_count / support_total, 2)
        if support_total > 0
        else None
    )
    if support_ratio is None:
        support_mode = "insufficient_data"
        support_summary = "No guardian response actions were observed in this period."
    elif support_ratio >= 0.67:
        support_mode = "support_heavy"
        support_summary = "Guardian interactions are mostly support-oriented."
    elif support_ratio >= 0.40:
        support_mode = "balanced"
        support_summary = "Guardian interactions are balanced between support and override."
    else:
        support_mode = "override_heavy"
        support_summary = "Guardian interactions are mostly override-oriented."

    return {
        "recovery_adoption_rate": {
            "rate": recovery_rate,
            "level": recovery_level,
            "adopted": recovery_adopted,
            "suggested": recovery_suggested,
            "pending": recovery_pending,
            "summary": recovery_summary,
        },
        "friction_load": {
            "score": friction_score,
            "level": friction_level,
            "components": {
                "repeated_skip": {
                    "count": repeated_skip_count,
                    "threshold": repeated_skip_threshold,
                    "load": round(repeated_skip_load, 2),
                },
                "l2_interruption": {
                    "count": l2_interrupt_count,
                    "threshold": l2_interrupt_threshold,
                    "load": round(l2_interrupt_load, 2),
                },
                "stagnation": {
                    "count": stagnation_days,
                    "threshold": stagnation_threshold,
                    "load": round(stagnation_load, 2),
                },
            },
            "summary": friction_summary,
        },
        "support_vs_override": {
            "support_count": support_count,
            "override_count": override_count,
            "total": support_total,
            "support_ratio": support_ratio,
            "mode": support_mode,
            "summary": support_summary,
        },
    }


def _recovery_adoption_within_hours(
    events: List[Dict[str, Any]],
    *,
    horizon_hours: int = 72,
) -> Dict[str, Any]:
    suggestions: List[Dict[str, Any]] = []
    completed_by_task: Dict[str, List[datetime]] = defaultdict(list)

    for event in events:
        event_type = event.get("type")
        if event_type == "task_recovery_suggested":
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            recovery_task_id = str(payload.get("recovery_task_id") or "").strip()
            parsed_time = _parse_event_time(event)
            if recovery_task_id and parsed_time:
                suggestions.append(
                    {"recovery_task_id": recovery_task_id, "parsed_time": parsed_time}
                )
            continue

        if _task_outcome_from_event(event) != "completed":
            continue
        task_id = _extract_task_id_from_event(event)
        parsed_time = _parse_event_time(event)
        if task_id and parsed_time:
            completed_by_task[task_id].append(parsed_time)

    for completed_times in completed_by_task.values():
        completed_times.sort()

    adopted = 0
    for suggestion in suggestions:
        recovery_task_id = suggestion["recovery_task_id"]
        suggested_at = suggestion["parsed_time"]
        deadline = suggested_at + timedelta(hours=horizon_hours)
        completion_times = completed_by_task.get(recovery_task_id, [])
        if any(suggested_at <= ts <= deadline for ts in completion_times):
            adopted += 1

    return {
        "suggested": len(suggestions),
        "adopted": adopted,
        "pending": max(0, len(suggestions) - adopted),
        "horizon_hours": horizon_hours,
    }


def _guardian_follow_through_adoption_rate(
    events: List[Dict[str, Any]],
    *,
    days: int,
    horizon_hours: int = 72,
) -> Dict[str, Any]:
    responses = _iter_guardian_response_events(events, days=days)
    confirmations = [
        entry
        for entry in responses
        if entry.get("action") == "confirm" and entry.get("parsed_time")
    ]
    if not confirmations:
        return {
            "confirmed": 0,
            "follow_through": 0,
            "rate": None,
            "horizon_hours": horizon_hours,
        }

    progress_times: List[datetime] = []
    for event in events:
        parsed_time = _parse_event_time(event)
        if not parsed_time:
            continue
        if _is_progress_event(event) or event.get("type") == "l2_session_completed":
            progress_times.append(parsed_time)
    progress_times.sort()

    followed_through = 0
    for confirmation in confirmations:
        confirmed_at = confirmation["parsed_time"]
        deadline = confirmed_at + timedelta(hours=horizon_hours)
        if any(confirmed_at <= ts <= deadline for ts in progress_times):
            followed_through += 1

    return {
        "confirmed": len(confirmations),
        "follow_through": followed_through,
        "rate": round(followed_through / len(confirmations), 2),
        "horizon_hours": horizon_hours,
    }


def _completed_l2_session_stats(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    lifecycle_events: List[Tuple[datetime, Dict[str, Any]]] = []
    for event in events:
        if event.get("type") not in {
            "l2_session_started",
            "l2_session_resumed",
            "l2_session_completed",
            "l2_session_interrupted",
        }:
            continue
        parsed_time = _parse_event_time(event)
        if not parsed_time:
            continue
        lifecycle_events.append((parsed_time, event))
    lifecycle_events.sort(key=lambda item: item[0])

    active_sessions: Dict[str, datetime] = {}
    total_minutes = 0.0
    completed_sessions = 0

    for parsed_time, event in lifecycle_events:
        event_type = event.get("type")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            fallback = str(event.get("event_id") or "").strip()
            if fallback:
                session_id = f"l2_session_{fallback}"
            else:
                session_id = f"l2_session_{int(parsed_time.timestamp())}"

        if event_type in {"l2_session_started", "l2_session_resumed"}:
            active_sessions[session_id] = parsed_time
            continue

        if event_type == "l2_session_interrupted":
            active_sessions.pop(session_id, None)
            continue

        if event_type != "l2_session_completed":
            continue

        session_started_at = active_sessions.pop(session_id, None)
        if session_started_at is None:
            continue
        if parsed_time < session_started_at:
            continue

        total_minutes += max(0.0, (parsed_time - session_started_at).total_seconds() / 60.0)
        completed_sessions += 1

    rounded_minutes = int(round(total_minutes))
    return {
        "completed_session_minutes": rounded_minutes,
        "completed_sessions": completed_sessions,
        "hours": round(rounded_minutes / 60.0, 2),
    }


def _split_current_previous_windows(
    events: List[Dict[str, Any]],
    *,
    now: datetime,
    days: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)

    current_events: List[Dict[str, Any]] = []
    previous_events: List[Dict[str, Any]] = []
    for event in events:
        parsed_time = _parse_event_time(event)
        if not parsed_time:
            continue
        if parsed_time >= current_start:
            current_events.append(event)
        elif previous_start <= parsed_time < current_start:
            previous_events.append(event)
    return current_events, previous_events


def _alignment_weekly_delta(days: int) -> Dict[str, Any]:
    lookback_days = max(days * 2, 14)
    trend = _goal_alignment_trend(load_events_for_period(lookback_days), lookback_days)
    points = trend.get("points") if isinstance(trend, dict) else []
    if not isinstance(points, list):
        points = []

    current_points = points[-days:] if len(points) >= days else points
    previous_points = (
        points[-(days * 2):-days] if len(points) >= (days * 2) else points[:-days]
    )

    def _avg_score(entries: List[Dict[str, Any]]) -> Optional[float]:
        values = [
            float(entry.get("avg_score"))
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("avg_score"), (int, float))
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    current_avg = _avg_score(current_points)
    previous_avg = _avg_score(previous_points)
    if current_avg is None or previous_avg is None:
        return {
            "delta": None,
            "current_week_avg": current_avg,
            "previous_week_avg": previous_avg,
            "summary": "Insufficient alignment samples for weekly delta.",
        }

    delta = round(current_avg - previous_avg, 2)
    if delta > 0:
        summary = "Alignment trend improved compared with previous week."
    elif delta < 0:
        summary = "Alignment trend declined compared with previous week."
    else:
        summary = "Alignment trend stayed flat compared with previous week."

    return {
        "delta": delta,
        "current_week_avg": current_avg,
        "previous_week_avg": previous_avg,
        "summary": summary,
    }


def _guardian_north_star_metrics(
    *,
    events: List[Dict[str, Any]],
    days: int,
    humanization_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    thresholds = {
        "mundane_automation_coverage": {"operator": ">=", "value": 0.55},
        "l2_bloom_hours": {"operator": ">=", "baseline_growth_ratio": 0.20},
        "human_trust_index": {"operator": ">=", "value": 0.65},
        "alignment_delta_weekly": {"operator": ">", "value": 0.0},
    }

    overdue_reschedules = 0
    skip_count = 0
    for event in events:
        if event.get("type") != "task_updated":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}

        status = str(updates.get("status") or "").strip().lower()
        if status == "skipped":
            skip_count += 1
        if str(meta.get("reason") or "").strip().lower() == "overdue_reschedule":
            overdue_reschedules += 1

    snooze_count = sum(
        1
        for entry in _iter_guardian_response_events(events, days=days)
        if entry.get("action") == "snooze"
    )
    l1_recovery_opportunities = overdue_reschedules + skip_count + snooze_count

    recovery_window = _recovery_adoption_within_hours(events, horizon_hours=72)
    adopted_auto_recovery = _coerce_int(
        recovery_window.get("adopted"),
        default=0,
        min_value=0,
        max_value=9999,
    )
    mundane_automation_coverage = (
        round(adopted_auto_recovery / l1_recovery_opportunities, 2)
        if l1_recovery_opportunities > 0
        else None
    )
    mundane_target = thresholds["mundane_automation_coverage"]["value"]
    mundane_met = (
        mundane_automation_coverage >= mundane_target
        if isinstance(mundane_automation_coverage, (int, float))
        else None
    )

    now = datetime.now()
    lookback_events = load_events_for_period(max(days * 2, 14))
    current_events, previous_events = _split_current_previous_windows(
        lookback_events,
        now=now,
        days=days,
    )
    l2_current = _completed_l2_session_stats(current_events)
    l2_previous = _completed_l2_session_stats(previous_events)
    baseline_hours = l2_previous["hours"]
    current_hours = l2_current["hours"]
    if isinstance(baseline_hours, (int, float)) and baseline_hours > 0:
        l2_growth_ratio = round((current_hours - baseline_hours) / baseline_hours, 2)
    else:
        l2_growth_ratio = None
    l2_growth_target = thresholds["l2_bloom_hours"]["baseline_growth_ratio"]
    l2_met = (
        l2_growth_ratio >= l2_growth_target
        if isinstance(l2_growth_ratio, (int, float))
        else None
    )

    support_payload = (
        humanization_metrics.get("support_vs_override")
        if isinstance(humanization_metrics, dict)
        else {}
    )
    if not isinstance(support_payload, dict):
        support_payload = {}
    friction_payload = (
        humanization_metrics.get("friction_load")
        if isinstance(humanization_metrics, dict)
        else {}
    )
    if not isinstance(friction_payload, dict):
        friction_payload = {}
    support_ratio = (
        float(support_payload.get("support_ratio"))
        if isinstance(support_payload.get("support_ratio"), (int, float))
        else None
    )
    friction_score = (
        float(friction_payload.get("score"))
        if isinstance(friction_payload.get("score"), (int, float))
        else None
    )
    follow_through = _guardian_follow_through_adoption_rate(
        events,
        days=days,
        horizon_hours=72,
    )
    adoption_rate = follow_through.get("rate")
    if (
        isinstance(support_ratio, (int, float))
        and isinstance(adoption_rate, (int, float))
        and isinstance(friction_score, (int, float))
    ):
        human_trust_index = round(
            (0.5 * support_ratio) + (0.3 * adoption_rate) + (0.2 * (1 - friction_score)),
            2,
        )
    else:
        human_trust_index = None
    trust_target = thresholds["human_trust_index"]["value"]
    trust_met = (
        human_trust_index >= trust_target
        if isinstance(human_trust_index, (int, float))
        else None
    )

    alignment_delta_payload = _alignment_weekly_delta(days)
    alignment_delta = alignment_delta_payload.get("delta")
    alignment_target = thresholds["alignment_delta_weekly"]["value"]
    alignment_met = (
        alignment_delta > alignment_target
        if isinstance(alignment_delta, (int, float))
        else None
    )

    met_values = [mundane_met, l2_met, trust_met, alignment_met]
    met_count = sum(1 for value in met_values if value is True)

    return {
        "window_days": days,
        "thresholds": thresholds,
        "mundane_automation_coverage": {
            "rate": mundane_automation_coverage,
            "adopted_auto_recovery": adopted_auto_recovery,
            "l1_recovery_opportunities": l1_recovery_opportunities,
            "opportunity_breakdown": {
                "overdue": overdue_reschedules,
                "skip": skip_count,
                "snooze": snooze_count,
            },
            "horizon_hours": recovery_window.get("horizon_hours", 72),
            "met_target": mundane_met,
        },
        "l2_bloom_hours": {
            "hours": current_hours,
            "completed_session_minutes": l2_current["completed_session_minutes"],
            "completed_sessions": l2_current["completed_sessions"],
            "baseline_hours": baseline_hours,
            "baseline_completed_session_minutes": l2_previous["completed_session_minutes"],
            "delta_ratio": l2_growth_ratio,
            "target_growth_ratio": l2_growth_target,
            "met_target": l2_met,
        },
        "human_trust_index": {
            "score": human_trust_index,
            "components": {
                "support_ratio": support_ratio,
                "adoption_rate": adoption_rate,
                "friction_score": friction_score,
            },
            "follow_through": follow_through,
            "met_target": trust_met,
        },
        "alignment_delta_weekly": {
            "delta": alignment_delta,
            "current_week_avg": alignment_delta_payload.get("current_week_avg"),
            "previous_week_avg": alignment_delta_payload.get("previous_week_avg"),
            "summary": alignment_delta_payload.get("summary"),
            "met_target": alignment_met,
        },
        "targets_met": {"met_count": met_count, "total": 4},
    }


def _signal_severity_rank(severity: str) -> int:
    normalized = str(severity or "").strip().lower()
    rank_map = {"high": 3, "medium": 2, "low": 1, "info": 0}
    return rank_map.get(normalized, 0)


def _highest_signal_severity(suggestion_sources: List[Dict[str, Any]]) -> str:
    highest = "info"
    highest_rank = -1
    for source in suggestion_sources:
        severity = str(source.get("severity") or "info").strip().lower()
        rank = _signal_severity_rank(severity)
        if rank > highest_rank:
            highest = severity
            highest_rank = rank
    return highest


def _guardian_policy_mode(
    *,
    latest_context: Optional[str],
    suggestion_sources: List[Dict[str, Any]],
) -> str:
    highest_severity = _highest_signal_severity(suggestion_sources)
    if latest_context == "instinct_escape" or highest_severity == "high":
        return "focused_override"
    if latest_context in {"recovering", "resource_blocked", "task_too_big"}:
        return "support_recovery"
    if not suggestion_sources:
        return "low_frequency_observe"
    return "balanced_intervention"


def _policy_mode_reason(mode: str, latest_context: Optional[str], highest_severity: str) -> str:
    if mode == "support_recovery":
        return (
            "Latest response context indicates recovery or blocker removal, "
            "so Guardian shifts to support-first cadence."
        )
    if mode == "focused_override":
        if latest_context == "instinct_escape":
            return "Instinct-escape context is active, so Guardian uses firm override cadence."
        return "High-severity deviation is active, so Guardian raises intervention intensity."
    if mode == "low_frequency_observe":
        return "No active intervention signal, so Guardian keeps low-frequency observation."
    if highest_severity == "medium":
        return "Medium-severity deviation is active, so Guardian uses balanced cadence."
    return "Guardian applies balanced cadence for current signal mix."


def _policy_cooldown_hours(mode: str, thresholds: Dict[str, Any]) -> int:
    if mode == "focused_override":
        return _coerce_int(
            thresholds.get("cadence_override_cooldown_hours"),
            default=3,
            min_value=1,
            max_value=168,
        )
    if mode == "support_recovery":
        return _coerce_int(
            thresholds.get("cadence_support_recovery_cooldown_hours"),
            default=8,
            min_value=1,
            max_value=168,
        )
    return _coerce_int(
        thresholds.get("cadence_observe_cooldown_hours"),
        default=12,
        min_value=1,
        max_value=168,
    )


def _guardian_intervention_policy(
    *,
    events: List[Dict[str, Any]],
    days: int,
    now: datetime,
    thresholds: Dict[str, Any],
    latest_context: Optional[str],
    suggestion_sources: List[Dict[str, Any]],
    display: bool,
    require_confirm: bool,
) -> Dict[str, Any]:
    mode = _guardian_policy_mode(
        latest_context=latest_context,
        suggestion_sources=suggestion_sources,
    )
    highest_severity = _highest_signal_severity(suggestion_sources)
    reason = _policy_mode_reason(mode, latest_context, highest_severity)

    responses = _iter_guardian_response_events(events, days=days)
    window_hours = _coerce_int(
        thresholds.get("reminder_budget_window_hours"),
        default=6,
        min_value=1,
        max_value=168,
    )
    max_prompts = _coerce_int(
        thresholds.get("reminder_budget_max_prompts"),
        default=2,
        min_value=1,
        max_value=24,
    )
    enforce_budget = _coerce_bool(thresholds.get("reminder_budget_enforce"), True)
    window_start = now - timedelta(hours=window_hours)
    recent_responses = [
        entry
        for entry in responses
        if entry.get("parsed_time") and entry["parsed_time"] >= window_start
    ]
    recent_prompt_count = len(recent_responses)
    budget_exceeded = recent_prompt_count >= max_prompts

    cooldown_hours = _policy_cooldown_hours(mode, thresholds)
    last_response_time = max(
        (entry.get("parsed_time") for entry in responses if entry.get("parsed_time")),
        default=None,
    )
    cooldown_active = False
    cooldown_remaining_minutes = 0
    if last_response_time:
        cooldown_ends_at = last_response_time + timedelta(hours=cooldown_hours)
        if now < cooldown_ends_at:
            cooldown_active = True
            cooldown_remaining_minutes = int(
                max(0, (cooldown_ends_at - now).total_seconds() // 60)
            )

    high_priority = mode == "focused_override" or highest_severity == "high"
    suppressed = (
        display
        and not high_priority
        and (
            (enforce_budget and budget_exceeded)
            or cooldown_active
        )
    )
    suppression_reason = None
    if suppressed:
        if enforce_budget and budget_exceeded:
            suppression_reason = "friction_budget_exceeded"
        elif cooldown_active:
            suppression_reason = "cooldown_active"

    effective_display = display and not suppressed
    effective_require_confirm = require_confirm and effective_display

    if mode == "focused_override":
        intensity = "firm"
    elif mode == "support_recovery":
        intensity = "supportive"
    else:
        intensity = "balanced"

    return {
        "mode": mode,
        "reason": reason,
        "highest_signal_severity": highest_severity,
        "intensity": intensity,
        "friction_budget": {
            "enabled": enforce_budget,
            "window_hours": window_hours,
            "max_prompts": max_prompts,
            "recent_prompt_count": recent_prompt_count,
            "budget_exceeded": budget_exceeded,
            "cooldown_hours": cooldown_hours,
            "cooldown_active": cooldown_active,
            "cooldown_remaining_minutes": cooldown_remaining_minutes,
            "suppressed": suppressed,
            "suppression_reason": suppression_reason,
        },
        "effective_display": effective_display,
        "effective_require_confirm": effective_require_confirm,
    }


def _build_guardian_explainability(
    *,
    display: bool,
    suggestion: str,
    require_confirm: bool,
    suggestion_sources: List[Dict[str, Any]],
    latest_response: Optional[Dict[str, Any]],
    guardian_role: Dict[str, Any],
    intervention_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    active_signals: List[str] = []
    for src in suggestion_sources[:2]:
        signal_name = str(src.get("signal") or "signal")
        count = src.get("count")
        threshold = src.get("threshold")
        if isinstance(count, (int, float)) and isinstance(threshold, (int, float)):
            active_signals.append(f"{signal_name} {int(count)}/{int(threshold)}")
        elif isinstance(count, (int, float)):
            active_signals.append(f"{signal_name} {int(count)}")
        else:
            active_signals.append(signal_name)

    if not display or not suggestion:
        why_this_suggestion = "No active intervention suggestion in this period."
    elif active_signals:
        why_this_suggestion = (
            "Suggestion is triggered by: "
            + ", ".join(active_signals)
            + "."
        )
    else:
        why_this_suggestion = suggestion

    if not display or not suggestion:
        what_happens_next = (
            "Guardian keeps observing rhythm and deviations for the next cycle."
        )
    elif require_confirm:
        what_happens_next = (
            "ASK mode is active: confirm this suggestion or respond with context."
        )
    elif latest_response and latest_response.get("action") == "confirm":
        what_happens_next = (
            "Suggestion is confirmed; follow-through will be checked in the next cycle."
        )
    elif latest_response and latest_response.get("action") in {"snooze", "dismiss"}:
        recovery_step = str(latest_response.get("recovery_step") or "").strip()
        if recovery_step:
            what_happens_next = f"Next suggested recovery step: {recovery_step}"
        else:
            what_happens_next = (
                "Response is recorded; Guardian will revisit when new evidence appears."
            )
    else:
        role_mode = str(guardian_role.get("mode") or "").strip().lower()
        if role_mode == "support_recovery":
            what_happens_next = (
                "Choose an action and context, then Guardian focuses on low-friction recovery."
            )
        elif role_mode == "overrule_instincts":
            what_happens_next = (
                "Choose an action and context, then Guardian prioritizes blueprint alignment."
            )
        else:
            what_happens_next = (
                "Choose confirm, snooze, or dismiss and the decision will be logged."
            )

    return {
        "why_this_suggestion": why_this_suggestion,
        "what_happens_next": what_happens_next,
        "active_signals": active_signals,
        "latest_action": latest_response.get("action") if latest_response else None,
        "why_now": (
            str((intervention_policy or {}).get("reason", "")).strip()
            if isinstance(intervention_policy, dict)
            else ""
        ),
        "intensity": (
            str((intervention_policy or {}).get("intensity", "")).strip()
            if isinstance(intervention_policy, dict)
            else ""
        ),
    }


def build_guardian_retrospective_response(days: int = 7) -> Dict[str, Any]:
    """
    返回带干预权限字段的复盘响应，供 API 使用。
    包含 intervention_level, suggestion, display, require_confirm。
    """
    raw = generate_guardian_retrospective(days)
    thresholds = _guardian_thresholds(days)
    generated_at = raw.get("generated_at")
    try:
        now = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except Exception:
        now = datetime.now()

    level = get_intervention_level()
    suggestion = (
        (raw["observations"][0] if raw["observations"] else "")
        if level != "OBSERVE_ONLY"
        else ""
    )
    display = level in ("SOFT", "ASK")
    require_confirm = level == "ASK"
    suggestion_sources = [
        {
            "signal": signal.get("name"),
            "severity": signal.get("severity"),
            "summary": signal.get("summary"),
            "count": signal.get("count", 0),
            "threshold": signal.get("threshold"),
            "evidence": signal.get("evidence", []),
        }
        for signal in raw.get("deviation_signals", [])
        if signal.get("active")
    ]
    fingerprint = _build_confirmation_fingerprint(raw)
    events_lookup_days = max(
        days,
        _coerce_int(
            thresholds.get("escalation_window_days"),
            default=days,
            min_value=1,
            max_value=30,
        ),
    )
    events = load_events_for_period(events_lookup_days)
    confirmation_event = _find_confirmation_event(
        events=events, days=days, fingerprint=fingerprint
    )
    latest_response = _find_guardian_response_event(
        events=events,
        days=days,
        fingerprint=fingerprint,
    )
    authority = _guardian_authority_snapshot(
        events=events,
        thresholds=thresholds,
        now=now,
    )

    confirmed = confirmation_event is not None
    confirmation_required = level == "ASK" and display and bool(suggestion)
    require_confirm = confirmation_required and not confirmed
    latest_context = latest_response.get("context") if latest_response else None
    guardian_role = _guardian_role_for_context(latest_context)
    intervention_policy = _guardian_intervention_policy(
        events=events,
        days=days,
        now=now,
        thresholds=thresholds,
        latest_context=latest_context,
        suggestion_sources=suggestion_sources,
        display=display and bool(suggestion),
        require_confirm=require_confirm,
    )
    display = bool(intervention_policy.get("effective_display", False)) and bool(suggestion)
    if not display:
        suggestion = ""

    latest_response_payload = (
        {
            "action": latest_response.get("action"),
            "timestamp": latest_response.get("timestamp"),
            "note": latest_response.get("note", ""),
            "fingerprint": latest_response.get("fingerprint"),
            "context": latest_response.get("context"),
            "context_label": latest_response.get("context_label"),
            "recovery_step": latest_response.get("recovery_step"),
        }
        if latest_response
        else None
    )
    allowed_actions = list(sorted(GUARDIAN_RESPONSE_ACTIONS)) if display and suggestion else []
    allowed_contexts = list(GUARDIAN_RESPONSE_CONTEXTS) if display and suggestion else []
    context_options = _guardian_context_options() if display and suggestion else []

    raw["intervention_level"] = level
    raw["suggestion"] = suggestion
    raw["display"] = display
    raw["require_confirm"] = require_confirm
    raw["suggestion_sources"] = suggestion_sources
    raw["intervention_policy"] = intervention_policy
    raw["response_action"] = {
        "required": confirmation_required,
        "pending": confirmation_required and not confirmed,
        "allowed_actions": allowed_actions,
        "allowed_contexts": allowed_contexts,
        "context_options": context_options,
        "default_context": "recovering",
        "latest": latest_response_payload,
        "endpoint": "/api/v1/retrospective/respond",
        "method": "POST",
        "fingerprint": fingerprint,
    }
    raw["confirmation_action"] = {
        "required": confirmation_required,
        "confirmed": confirmed,
        "confirmed_at": confirmation_event.get("timestamp") if confirmed else None,
        "endpoint": "/api/v1/retrospective/confirm",
        "method": "POST",
        "fingerprint": fingerprint,
    }
    raw["guardian_role"] = guardian_role
    l2_session = raw.get("l2_session") if isinstance(raw.get("l2_session"), dict) else {}
    resume_session_id = l2_session.get("resume_session_id")
    resume_hint = str(l2_session.get("resume_hint") or "").strip() or None
    raw["l2_session_action"] = {
        "active": bool(l2_session.get("active_session")),
        "active_session_id": l2_session.get("active_session_id"),
        "start": {"endpoint": "/api/v1/l2/session/start", "method": "POST"},
        "resume": {
            "enabled": bool(l2_session.get("resume_ready")),
            "session_id": resume_session_id,
            "minimal_step": resume_hint,
            "endpoint": "/api/v1/l2/session/resume",
            "method": "POST",
        },
        "interrupt": {
            "endpoint": "/api/v1/l2/session/interrupt",
            "method": "POST",
            "reason_options": _l2_session_interrupt_reason_options(),
        },
        "complete": {"endpoint": "/api/v1/l2/session/complete", "method": "POST"},
        "ritual": {
            "start_intention_prompt": (
                "Define the one concrete outcome for this focus session before starting."
            ),
            "complete_reflection_prompt": (
                "Capture one reflection on what moved long-term value forward."
            ),
        },
        "micro_ritual": (
            l2_session.get("micro_ritual")
            if isinstance(l2_session.get("micro_ritual"), dict)
            else {}
        ),
    }
    metrics_events = events if events_lookup_days == days else load_events_for_period(days)
    raw["humanization_metrics"] = _guardian_humanization_metrics(
        events=metrics_events,
        days=days,
        deviation_signals=raw.get("deviation_signals"),
    )
    raw["north_star_metrics"] = _guardian_north_star_metrics(
        events=metrics_events,
        days=days,
        humanization_metrics=raw["humanization_metrics"],
    )
    raw["blueprint_narrative"] = _blueprint_narrative_loop(
        events=metrics_events,
        deviation_signals=raw.get("deviation_signals", []),
        north_star_metrics=raw["north_star_metrics"],
        l2_session=l2_session,
        alignment=raw.get("alignment", {}),
    )
    raw["explainability"] = _build_guardian_explainability(
        display=display,
        suggestion=suggestion,
        require_confirm=require_confirm,
        suggestion_sources=suggestion_sources,
        latest_response=latest_response_payload,
        guardian_role=guardian_role,
        intervention_policy=intervention_policy,
    )
    raw["authority"] = authority
    return raw
