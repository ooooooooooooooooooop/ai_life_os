"""
Retrospective Engine for AI Life OS.

Generates execution reports and improvement suggestions.
Analyzes failure patterns and user behavior.

GuardianRetrospective: derived view from event_log (read-only), four dimensions:
rhythm, alignment, friction, observations.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    sorted_dates = sorted(daily.keys())
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
        if ev.get("type") in ("goal_confirmed", "goal_rejected", "goal_completed", "goal_feedback", "goal_action"):
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
    deviated = rejected > 0 or (linked > 0 and sum(1 for ev in events if ev.get("type") == "goal_completed") < linked)
    summary = "执行与愿景/目标方向一致。" if not deviated else "存在拒绝或未完成与愿景相关的目标，可回顾当前重心。"
    return {"deviated": deviated, "summary": summary}


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
) -> List[str]:
    """1–3 条 Guardian 观察，由三维度派生，不硬编码固定文案。"""
    out = []
    if rhythm.get("broken"):
        out.append(rhythm.get("summary", "本周期内存在多日无执行记录，节律可能断裂。"))
    if alignment.get("deviated"):
        out.append(alignment.get("summary", "部分与愿景相关的目标被跳过或拒绝，可回顾是否与当前重心一致。"))
    if friction.get("repeated_skip"):
        out.append(friction.get("summary", "存在多次跳过任务，建议拆分为更小步骤或调整优先级。"))
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
    friction = _guardian_friction(events)
    observations = _guardian_observations(rhythm, alignment, friction)

    return {
        "period": {"days": days, "start_date": start_date, "end_date": end_date},
        "generated_at": now.isoformat(),
        "rhythm": rhythm,
        "alignment": alignment,
        "friction": friction,
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


def build_guardian_retrospective_response(days: int = 7) -> Dict[str, Any]:
    """
    返回带干预权限字段的复盘响应，供 API 使用。
    包含 intervention_level, suggestion, display, require_confirm。
    """
    raw = generate_guardian_retrospective(days)
    level = get_intervention_level()
    suggestion = (raw["observations"][0] if raw["observations"] else "") if level != "OBSERVE_ONLY" else ""
    display = level in ("SOFT", "ASK")
    require_confirm = level == "ASK"
    raw["intervention_level"] = level
    raw["suggestion"] = suggestion
    raw["display"] = display
    raw["require_confirm"] = require_confirm
    return raw
