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

from core.config_manager import config
from core.event_sourcing import EVENT_LOG_PATH, rebuild_state
from core.llm_adapter import get_llm


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


def _guardian_l2_protection(events: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    """
    L2 protection ratio:
    During deep_work window, how many L2 task outcomes are protected (completed)
    vs interrupted (skipped).
    """
    goal_type_by_goal_id, task_goal_by_task_id = _build_l2_reference_maps()

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
    elif ratio >= 0.75:
        level = "high"
        summary = "L2 保护表现良好，深度工作时段执行稳定。"
    elif ratio >= 0.50:
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
    }


def _detect_deviation_signals(events: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    """
    Detect behavior deviation signals and provide traceable evidence.
    """
    skip_events: List[Dict[str, Any]] = []
    l2_interruptions: List[Dict[str, Any]] = []
    progress_events: List[Dict[str, Any]] = []

    for event in events:
        event_time = _parse_event_time(event)

        if _is_task_skip_event(event):
            skip_events.append(event)
            if event_time and _phase_for_time(event_time) == "deep_work":
                l2_interruptions.append(event)

        if _is_progress_event(event):
            progress_events.append(event)

    repeated_skip_count = len(skip_events)
    repeated_skip_active = repeated_skip_count >= 2

    l2_interruption_count = len(l2_interruptions)
    l2_interruption_active = l2_interruption_count >= 1

    now = datetime.now()
    recent_progress_time = max(
        (_parse_event_time(ev) for ev in progress_events if _parse_event_time(ev)),
        default=None,
    )
    stagnation_threshold_days = 3 if days >= 3 else 1
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
            "threshold": 2,
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
            "threshold": 1,
            "summary": (
                f"深度工作时段检测到 {l2_interruption_count} 次跳过，存在 L2 执行中断。"
                if l2_interruption_active
                else "未检测到深度工作时段中断信号。"
            ),
            "evidence": [
                _event_evidence(ev, f"skip during {_phase_for_time(_parse_event_time(ev) or now)}")
                for ev in l2_interruptions[-3:]
            ],
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

    rhythm = _guardian_rhythm(events, days)
    alignment = _guardian_alignment(events)
    alignment["trend"] = _goal_alignment_trend(events, days)
    friction = _guardian_friction(events)
    l2_protection = _guardian_l2_protection(events, days)
    deviation_signals = _detect_deviation_signals(events, days)
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
        "deviation_signals": deviation_signals,
        "observations": observations,
    }


def get_intervention_level() -> str:
    """从 config/blueprint.yaml 读取 intervention_level：OBSERVE_ONLY | SOFT | ASK。默认 SOFT。"""
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "blueprint.yaml"
    if not config_path.exists():
        return "SOFT"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        level = data.get("intervention_level", "SOFT")
        if level in ("OBSERVE_ONLY", "SOFT", "ASK"):
            return level
    except Exception:
        pass
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


def _find_confirmation_event(
    events: List[Dict[str, Any]],
    days: int,
    fingerprint: str,
) -> Optional[Dict[str, Any]]:
    """
    Find the latest matching ASK confirmation event in current lookback window.
    """
    for event in reversed(events):
        if event.get("type") != "guardian_intervention_confirmed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        payload_days = payload.get("days")
        if payload_days is not None:
            try:
                if int(payload_days) != int(days):
                    continue
            except (TypeError, ValueError):
                continue
        if payload.get("fingerprint") == fingerprint:
            return event
    return None


def build_guardian_retrospective_response(days: int = 7) -> Dict[str, Any]:
    """
    返回带干预权限字段的复盘响应，供 API 使用。
    包含 intervention_level, suggestion, display, require_confirm。
    """
    raw = generate_guardian_retrospective(days)
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
    events = load_events_for_period(days)
    confirmation_event = _find_confirmation_event(
        events=events, days=days, fingerprint=fingerprint
    )
    confirmed = confirmation_event is not None
    confirmation_required = level == "ASK" and display and bool(suggestion)
    require_confirm = confirmation_required and not confirmed

    raw["intervention_level"] = level
    raw["suggestion"] = suggestion
    raw["display"] = display
    raw["require_confirm"] = require_confirm
    raw["suggestion_sources"] = suggestion_sources
    raw["confirmation_action"] = {
        "required": confirmation_required,
        "confirmed": confirmed,
        "confirmed_at": confirmation_event.get("timestamp") if confirmed else None,
        "endpoint": "/api/v1/retrospective/confirm",
        "method": "POST",
        "fingerprint": fingerprint,
    }
    return raw
