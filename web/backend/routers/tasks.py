from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.event_sourcing import append_event, rebuild_state
from core.goal_service import GoalService
from core.models import TaskStatus
from core.task_dispatcher import TaskDispatcher

router = APIRouter()


class ActionRequest(BaseModel):
    reason: Optional[str] = None
    feedback_type: Optional[str] = None


class ProgressRequest(BaseModel):
    message: str


def _resolve_goal_title(goal_id: str, state) -> str:
    service = GoalService()
    node = service.get_node(goal_id)
    if node:
        return node.title

    for goal in state.get("goals", []):
        if getattr(goal, "id", None) == goal_id:
            return getattr(goal, "title", "Unknown Goal")

    return "Unknown Goal"


@router.get("/current")
def get_current_task():
    state = rebuild_state()
    dispatcher = TaskDispatcher()
    current_task = dispatcher.get_current_task(state.get("tasks", []))

    if not current_task:
        return {"task": None, "reason": "No pending tasks or all scheduled for future"}

    result = current_task.__dict__.copy()
    result["goal_title"] = _resolve_goal_title(current_task.goal_id, state)
    return {"task": result}


@router.post("/{task_id}/complete")
def complete_task(task_id: str):
    append_event(
        {
            "type": "task_updated",
            "payload": {
                "id": task_id,
                "updates": {
                    "status": TaskStatus.COMPLETED,
                    "completed_at": datetime.now().isoformat(),
                },
            },
        }
    )

    append_event(
        {
            "type": "execution_completed",
            "payload": {
                "id": f"exec_{task_id}_{int(datetime.now().timestamp())}",
                "outcome": "completed",
                "completed_at": datetime.now().isoformat(),
            },
        }
    )

    return get_current_task()


@router.post("/{task_id}/skip")
def skip_task(task_id: str, req: ActionRequest):
    append_event(
        {
            "type": "task_updated",
            "payload": {
                "id": task_id,
                "updates": {
                    "status": TaskStatus.SKIPPED,
                    "skip_reason": req.reason or "skipped_by_user",
                },
            },
        }
    )
    return get_current_task()


@router.post("/progress")
def update_progress(req: ProgressRequest):
    append_event(
        {
            "type": "progress_updated",
            "payload": {
                "message": req.message,
                "raw_text": req.message,
            },
        }
    )
    return {"status": "recorded", "message": "Progress logged"}


@router.get("/list")
def list_tasks():
    state = rebuild_state()
    tasks = state.get("tasks", [])

    pending = []
    completed = []
    for task in tasks:
        task_dict = task.__dict__.copy()
        task_dict["goal_title"] = _resolve_goal_title(task.goal_id, state)

        if task.status == TaskStatus.PENDING:
            pending.append(task_dict)
        elif task.status == TaskStatus.COMPLETED:
            completed.append(task_dict)

    return {
        "pending": pending,
        "completed": completed,
        "total": len(tasks),
    }
