from datetime import date, timedelta

from core.models import Task, TaskStatus
from core.task_dispatcher import TaskDispatcher


def _task(
    task_id: str,
    goal_id: str,
    scheduled_date: date,
    *,
    status: TaskStatus = TaskStatus.PENDING,
    scheduled_time: str = "Anytime",
) -> Task:
    return Task(
        id=task_id,
        goal_id=goal_id,
        description=f"task-{task_id}",
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        estimated_minutes=30,
        status=status,
    )


def test_reschedule_overdue_updates_only_pending_active_goal_tasks():
    dispatcher = TaskDispatcher()
    today = date.today()
    tasks = [
        _task("t_active_overdue", "g_active", today - timedelta(days=2), scheduled_time="09:00"),
        _task("t_active_today", "g_active", today, scheduled_time="10:00"),
        _task(
            "t_inactive_overdue",
            "g_inactive",
            today - timedelta(days=1),
            scheduled_time="11:00",
        ),
        _task(
            "t_completed_overdue",
            "g_active",
            today - timedelta(days=3),
            status=TaskStatus.COMPLETED,
            scheduled_time="08:00",
        ),
    ]

    updates = dispatcher.reschedule_overdue(tasks, active_goals_ids=["g_active"])

    assert len(updates) == 1
    assert updates[0]["id"] == "t_active_overdue"
    assert updates[0]["updates"]["scheduled_date"] == today.isoformat()
    assert updates[0]["updates"]["scheduled_time"] == "09:00"
    assert updates[0]["meta"]["reason"] == "overdue_reschedule"


def test_reschedule_overdue_uses_anytime_when_scheduled_time_missing():
    dispatcher = TaskDispatcher()
    today = date.today()
    task = _task("t_missing_time", "g1", today - timedelta(days=1), scheduled_time="")

    updates = dispatcher.reschedule_overdue([task], active_goals_ids=["g1"])

    assert len(updates) == 1
    assert updates[0]["updates"]["scheduled_time"] == "Anytime"
