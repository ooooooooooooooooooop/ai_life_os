"""
Rhythm Detector for AI Life OS.

Analyzes event history to detect behavioral patterns and habits.
Provides structured data for the Steward to generate rhythm-based actions.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.event_sourcing import EVENT_LOG_PATH
from core.config_manager import config


def load_events(days_back: int = 30) -> List[Dict[str, Any]]:
    """
    Load events from the event log.

    Args:
        days_back: Number of days to look back (default: 30, 经验值)

    Returns:
        List of event dictionaries.
    """
    if not EVENT_LOG_PATH.exists():
        return []

    cutoff_date = datetime.now() - timedelta(days=days_back)
    events = []

    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                # 过滤旧事件
                timestamp_str = event.get("timestamp", "")
                if timestamp_str:
                    try:
                        event_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if event_time.replace(tzinfo=None) >= cutoff_date:
                            events.append(event)
                    except ValueError:
                        events.append(event)  # 无法解析时间，保留
                else:
                    events.append(event)
            except json.JSONDecodeError:
                continue

    return events


def analyze_task_completion(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze task completion patterns.

    Returns:
        Dict mapping task descriptions to their statistics.
    """
    task_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"completed": 0, "failed": 0, "times": []}
    )

    for event in events:
        event_type = event.get("type", "")

        if event_type == "task_completed":
            task_id = event.get("task_id", "")
            # 提取时间
            timestamp = event.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M")
                    task_stats[task_id]["completed"] += 1
                    task_stats[task_id]["times"].append(time_str)
                except ValueError:
                    task_stats[task_id]["completed"] += 1
            else:
                task_stats[task_id]["completed"] += 1

        elif event_type == "task_failed":
            task_id = event.get("task_id", "")
            task_stats[task_id]["failed"] += 1

    return dict(task_stats)


def detect_time_patterns(events: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Detect time-based patterns in user activity.

    Returns:
        Dict mapping time slots to typical actions.
    """
    time_slots: Dict[str, List[str]] = defaultdict(list)

    for event in events:
        if event.get("type") != "task_completed":
            continue

        timestamp = event.get("timestamp", "")
        if not timestamp:
            continue

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            # 按小时分组
            hour = dt.hour
            if 5 <= hour < 9:
                slot = "早晨"
            elif 9 <= hour < 12:
                slot = "上午"
            elif 12 <= hour < 14:
                slot = "午间"
            elif 14 <= hour < 18:
                slot = "下午"
            elif 18 <= hour < 21:
                slot = "晚间"
            else:
                slot = "深夜"

            task_id = event.get("task_id", "")
            time_slots[slot].append(task_id)
        except ValueError:
            continue

    return dict(time_slots)


def calculate_success_rate(task_stats: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate success rate for each task.

    Returns:
        Dict mapping task_id to success rate (0.0 - 1.0).
    """
    rates = {}
    for task_id, stats in task_stats.items():
        total = stats["completed"] + stats["failed"]
        if total >= config.STATS_MIN_SAMPLE_SIZE:  # 使用配置的样本量阈值
            rates[task_id] = stats["completed"] / total
    return rates


def find_preferred_times(task_stats: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Find preferred execution times for tasks.

    Returns:
        Dict mapping task_id to preferred time range.
    """
    preferred = {}

    for task_id, stats in task_stats.items():
        times = stats.get("times", [])
        if len(times) < config.STATS_MIN_SAMPLE_SIZE:  # 样本太少
            continue

        # 简单策略：取最频繁的小时
        hour_counts: Dict[int, int] = defaultdict(int)
        for t in times:
            try:
                hour = int(t.split(":")[0])
                hour_counts[hour] += 1
            except (ValueError, IndexError):
                continue

        if hour_counts:
            best_hour = max(hour_counts, key=hour_counts.get)
            preferred[task_id] = f"{best_hour:02d}:00-{(best_hour+1) % 24:02d}:00"

    return preferred


def detect_habits(min_occurrences: int = None) -> Dict[str, Any]:
    """
    Main function to detect user habits from event history.

    Args:
        min_occurrences: Minimum number of occurrences to consider a habit
                         (默认从 config.HABIT_MIN_OCCURRENCES 获取)

    Returns:
        Structured habit data for use by Steward.
    """
    if min_occurrences is None:
        min_occurrences = config.HABIT_MIN_OCCURRENCES

    events = load_events(days_back=30)

    if not events:
        return {
            "detected_habits": [],
            "success_rates": {},
            "preferred_times": {},
            "time_patterns": {}
        }

    task_stats = analyze_task_completion(events)
    success_rates = calculate_success_rate(task_stats)
    preferred_times = find_preferred_times(task_stats)
    time_patterns = detect_time_patterns(events)

    # 识别习惯：完成次数 >= min_occurrences 且成功率 >= 0.6
    detected_habits = []
    for task_id, stats in task_stats.items():
        total = stats["completed"] + stats["failed"]
        if total >= min_occurrences:
            rate = success_rates.get(task_id, 0)
            if rate >= config.HABIT_SUCCESS_RATE_THRESHOLD:  # 使用配置的成功率阈值
                habit = {
                    "task_id": task_id,
                    "occurrences": total,
                    "success_rate": round(rate, 2),
                    "preferred_time": preferred_times.get(task_id),
                    "confidence": min(1.0, total / 10)  # 基于样本量的置信度
                }
                detected_habits.append(habit)

    # 按置信度排序
    detected_habits.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "detected_habits": detected_habits,
        "success_rates": success_rates,
        "preferred_times": preferred_times,
        "time_patterns": time_patterns
    }


def get_rhythm_suggestions(max_suggestions: int = 3) -> List[Dict[str, Any]]:
    """
    Generate rhythm-based action suggestions.

    Args:
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of suggested actions based on detected habits.
    """
    habits_data = detect_habits()
    suggestions = []

    for habit in habits_data["detected_habits"][:max_suggestions]:
        task_id = habit["task_id"]
        preferred_time = habit.get("preferred_time")

        suggestion = {
            "id": f"rhythm_{task_id}_{datetime.now().strftime('%Y%m%d')}",
            "description": f"继续执行: {task_id}",
            "priority": "rhythm",
            "question_type": "yes_no",
            "based_on": {
                "occurrences": habit["occurrences"],
                "success_rate": habit["success_rate"],
                "preferred_time": preferred_time
            }
        }
        suggestions.append(suggestion)

    return suggestions
