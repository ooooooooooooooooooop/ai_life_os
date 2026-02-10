"""
Task Dispatcher for AI Life OS.
Selects the current best task to present to the user based on schedule and context.
"""
from datetime import datetime
from typing import List, Optional
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

    def reschedule_overdue(self, tasks: List[Task], active_goals_ids: List[str]) -> List[Task]:
        """
        简单重排过期任务（暂未实现，Phase 3）
        """
        pass
