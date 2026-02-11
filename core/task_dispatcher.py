"""
Task Dispatcher for AI Life OS.
Selects the current best task to present to the user based on schedule and context.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from core.models import Task, TaskStatus

class TaskDispatcher:
    """任务调度器"""

    def get_current_task(self, tasks: List[Task], current_time: datetime = None) -> Optional[Task]:
        """
        获取当前应该执行的任务。
        策略：
        1. 必须是 PENDING 状态
        2. scheduled_date <= 今天 (包括过期的)
        3. 优先显示 scheduled_time 接近当前时间的
        4. 如果有多个，优先显示最早过期的
        """
        if current_time is None:
            current_time = datetime.now()

        today = current_time.date()

        candidates = [
            t for t in tasks
            if t.status == TaskStatus.PENDING
            and t.scheduled_date <= today
        ]

        if not candidates:
            return None

        # 排序逻辑：
        # 1. 过期任务优先 (date 小的在前)
        # 2. 同日期的，按时间排序 (简单的字符串比较，暂时够用)
        # 3. 如果时间是 'Anytime'，放最后

        def sort_key(t: Task):
            date_score = t.scheduled_date.toordinal()

            # Simple time heuristic
            time_score = 9999
            if t.scheduled_time and ":" in t.scheduled_time:
                try:
                    # Parse HH:MM to minutes
                    h, m = map(int, t.scheduled_time.split(":"))
                    time_score = h * 60 + m
                except (TypeError, ValueError):
                    pass
            elif t.scheduled_time == "Morning":
                time_score = 9 * 60
            elif t.scheduled_time == "Afternoon":
                time_score = 14 * 60
            elif t.scheduled_time == "Evening":
                time_score = 20 * 60

            return (date_score, time_score)

        candidates.sort(key=sort_key)

        return candidates[0]

    @staticmethod
    def _normalized_date(value: Any) -> Optional[date]:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _status_value(status: Any) -> str:
        if hasattr(status, "value"):
            return str(getattr(status, "value", "")).lower()
        return str(status or "").lower()

    def reschedule_overdue(
        self,
        tasks: List[Task],
        active_goals_ids: List[str],
        current_time: datetime = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect overdue task updates for deterministic replay:
        - only pending tasks
        - only tasks tied to active goals (if active goal list provided)
        - reschedule overdue date to today while preserving time preference
        """
        if current_time is None:
            current_time = datetime.now()
        today = current_time.date()
        active_goal_set = {str(goal_id) for goal_id in active_goals_ids if goal_id}
        updates: List[Dict[str, Any]] = []

        for task in tasks:
            if self._status_value(getattr(task, "status", None)) != TaskStatus.PENDING.value:
                continue

            task_goal_id = str(getattr(task, "goal_id", "") or "")
            if active_goal_set and task_goal_id not in active_goal_set:
                continue

            scheduled_date = self._normalized_date(getattr(task, "scheduled_date", None))
            if scheduled_date is None or scheduled_date >= today:
                continue

            scheduled_time = getattr(task, "scheduled_time", None) or "Anytime"
            updates.append(
                {
                    "id": getattr(task, "id", None),
                    "updates": {
                        "scheduled_date": today.isoformat(),
                        "scheduled_time": scheduled_time,
                    },
                    "meta": {
                        "reason": "overdue_reschedule",
                        "previous_date": scheduled_date.isoformat(),
                    },
                }
            )

        return updates
