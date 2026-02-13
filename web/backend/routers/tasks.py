from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.event_sourcing import append_event, rebuild_state
from core.goal_service import GoalService
from core.models import TaskStatus
from core.retrospective import build_guardian_retrospective_response
from core.task_dispatcher import TaskDispatcher

router = APIRouter()
ALLOWED_SKIP_CONTEXTS = {
    "recovering",
    "resource_blocked",
    "task_too_big",
    "instinct_escape",
}
RECOVERY_MINUTES_BY_CONTEXT = {
    "recovering": 10,
    "resource_blocked": 15,
    "task_too_big": 15,
    "instinct_escape": 10,
}


class ActionRequest(BaseModel):
    reason: Optional[str] = None
    feedback_type: Optional[str] = None
    context: Optional[str] = None


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


def _normalize_skip_context(raw_context: Optional[str]) -> Optional[str]:
    context = str(raw_context or "").strip().lower()
    if not context:
        return None
    if context not in ALLOWED_SKIP_CONTEXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "context must be one of recovering | resource_blocked | "
                "task_too_big | instinct_escape"
            ),
        )
    return context


def _status_value(status: Any) -> str:
    if hasattr(status, "value"):
        return str(getattr(status, "value", "")).lower()
    return str(status or "").lower()


def _active_goal_ids(state: Dict[str, Any]) -> List[str]:
    goal_ids = []
    for goal in state.get("goals", []):
        if _status_value(getattr(goal, "status", None)) == "active":
            goal_id = getattr(goal, "id", None)
            if goal_id:
                goal_ids.append(str(goal_id))
    return goal_ids


def _find_task(state: Dict[str, Any], task_id: str):
    for task in state.get("tasks", []):
        if str(getattr(task, "id", "")) == str(task_id):
            return task
    return None


def _guardian_dispatch_context(days: int = 7) -> Dict[str, Any]:
    try:
        retrospective = build_guardian_retrospective_response(days=days)
    except Exception:
        retrospective = {}
    if not isinstance(retrospective, dict):
        retrospective = {}

    policy = retrospective.get("intervention_policy")
    if not isinstance(policy, dict):
        policy = {}
    trust_repair = policy.get("trust_repair")
    if not isinstance(trust_repair, dict):
        trust_repair = {}

    mode = str(policy.get("mode") or "").strip().lower()
    trust_repair_active = mode == "trust_repair" or bool(trust_repair.get("active"))
    repair_min_step = str(trust_repair.get("repair_min_step") or "").strip() or None
    return {
        "mode": mode or "balanced_intervention",
        "low_pressure": trust_repair_active,
        "prioritize_recovery": trust_repair_active,
        "repair_min_step": repair_min_step,
    }


def _reschedule_overdue_tasks(
    state: Dict[str, Any],
    dispatcher: TaskDispatcher,
    *,
    low_pressure: bool = False,
) -> Dict[str, Any]:
    updates = dispatcher.reschedule_overdue(
        state.get("tasks", []),
        active_goals_ids=_active_goal_ids(state),
        low_pressure=low_pressure,
    )
    if not updates:
        return state
    for update in updates:
        append_event(
            {
                "type": "task_updated",
                "payload": {
                    "id": update.get("id"),
                    "updates": update.get("updates", {}),
                    "meta": update.get("meta", {}),
                },
            }
        )
    return rebuild_state()


def _minimal_recovery_description(
    *,
    goal_title: str,
    original_description: str,
    context: Optional[str],
) -> str:
    normalized = context or "recovering"
    if normalized == "resource_blocked":
        return (
            f"[Recovery] 为目标「{goal_title}」解除阻塞：确认所需资源并完成一项可立即执行准备。"
        )
    if normalized == "task_too_big":
        return (
            f"[Recovery] 将任务「{original_description}」拆成最小下一步，并先执行第一步。"
        )
    if normalized == "instinct_escape":
        return (
            f"[Recovery] 关闭干扰后，先执行「{original_description}」10 分钟重启专注。"
        )
    return f"[Recovery] 恢复后重启目标「{goal_title}」：先完成一个 10 分钟最小动作。"


def _split_candidates_for_big_task(original_description: str) -> List[str]:
    task_text = original_description.strip() or "当前任务"
    return [
        f"明确完成标准：写下「{task_text}」的可交付结果（1-2 句）。",
        f"准备执行环境：只完成与「{task_text}」直接相关的一项准备。",
        f"启动最小动作：投入 10 分钟处理「{task_text}」的第一步。",
    ]


def _create_skip_recovery_task(task_id: str, context: Optional[str]) -> Optional[str]:
    state = rebuild_state()
    original = _find_task(state, task_id)
    if not original:
        return None

    recovery_id = f"{task_id}_recovery"
    if _find_task(state, recovery_id):
        return recovery_id

    goal_id = str(getattr(original, "goal_id", "") or "")
    goal_title = _resolve_goal_title(goal_id, state)
    original_description = str(getattr(original, "description", "") or "当前任务")
    split_candidates = (
        _split_candidates_for_big_task(original_description)
        if context == "task_too_big"
        else []
    )
    now_iso = datetime.now().isoformat()
    append_event(
        {
            "type": "task_created",
            "payload": {
                "task": {
                    "id": recovery_id,
                    "goal_id": goal_id,
                    "description": _minimal_recovery_description(
                        goal_title=goal_title,
                        original_description=original_description,
                        context=context,
                    ),
                    "scheduled_date": datetime.now().date().isoformat(),
                    "scheduled_time": "Anytime",
                    "estimated_minutes": RECOVERY_MINUTES_BY_CONTEXT.get(
                        context or "recovering",
                        10,
                    ),
                    "status": TaskStatus.PENDING,
                    "created_at": now_iso,
                }
            },
        }
    )
    append_event(
        {
            "type": "task_recovery_suggested",
            "timestamp": now_iso,
            "payload": {
                "source_task_id": task_id,
                "recovery_task_id": recovery_id,
                "goal_id": goal_id,
                "context": context or "recovering",
                "reason": "skip_recovery_minimal_step",
                "split_candidates": split_candidates,
            },
        }
    )
    if split_candidates:
        append_event(
            {
                "type": "task_split_candidates_suggested",
                "timestamp": now_iso,
                "payload": {
                    "source_task_id": task_id,
                    "recovery_task_id": recovery_id,
                    "goal_id": goal_id,
                    "context": context,
                    "candidates": split_candidates,
                },
            }
        )
    return recovery_id


def _pending_recovery_tasks(state: Dict[str, Any]) -> List[Any]:
    out = []
    for task in state.get("tasks", []):
        task_id = str(getattr(task, "id", "") or "")
        status = _status_value(getattr(task, "status", None))
        if status != TaskStatus.PENDING.value:
            continue
        if not task_id.endswith("_recovery"):
            continue
        out.append(task)
    return out


def _task_preview_payload(task: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": getattr(task, "id", ""),
        "goal_id": getattr(task, "goal_id", ""),
        "goal_title": _resolve_goal_title(getattr(task, "goal_id", ""), state),
        "description": getattr(task, "description", ""),
        "scheduled_date": str(getattr(task, "scheduled_date", "")),
        "scheduled_time": getattr(task, "scheduled_time", "Anytime"),
        "estimated_minutes": getattr(task, "estimated_minutes", 10),
    }


def _apply_recovery_batch_updates(state: Dict[str, Any]) -> Dict[str, Any]:
    candidates = _pending_recovery_tasks(state)
    if not candidates:
        return {"applied_count": 0, "task_ids": []}

    today_iso = datetime.now().date().isoformat()
    applied_ids: List[str] = []
    for task in candidates:
        task_id = str(getattr(task, "id", "") or "")
        scheduled_date = str(getattr(task, "scheduled_date", "") or "")
        scheduled_time = str(getattr(task, "scheduled_time", "") or "Anytime")
        if scheduled_date == today_iso and scheduled_time == "Anytime":
            continue
        append_event(
            {
                "type": "task_updated",
                "payload": {
                    "id": task_id,
                    "updates": {
                        "scheduled_date": today_iso,
                        "scheduled_time": "Anytime",
                    },
                    "meta": {
                        "reason": "recovery_batch_apply",
                        "batch": True,
                    },
                },
            }
        )
        applied_ids.append(task_id)
    return {"applied_count": len(applied_ids), "task_ids": applied_ids}


@router.get("/current")
def get_current_task():
    dispatcher = TaskDispatcher()
    dispatch_context = _guardian_dispatch_context()
    state = rebuild_state()
    state = _reschedule_overdue_tasks(
        state,
        dispatcher,
        low_pressure=bool(dispatch_context.get("low_pressure")),
    )
    current_task = dispatcher.get_current_task(
        state.get("tasks", []),
        prioritize_recovery=bool(dispatch_context.get("prioritize_recovery")),
    )

    if not current_task:
        payload = {"task": None, "reason": "No pending tasks or all scheduled for future"}
        if dispatch_context.get("low_pressure"):
            payload["dispatch_policy"] = dispatch_context
        return payload

    result = current_task.__dict__.copy()
    result["goal_title"] = _resolve_goal_title(current_task.goal_id, state)
    payload = {"task": result}
    if dispatch_context.get("low_pressure"):
        payload["dispatch_policy"] = dispatch_context
    return payload


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
    context = _normalize_skip_context(req.context)
    context_value = context or "recovering"
    append_event(
        {
            "type": "task_updated",
            "payload": {
                "id": task_id,
                "updates": {
                    "status": TaskStatus.SKIPPED,
                    "skip_reason": req.reason or "skipped_by_user",
                    "skip_context": context_value,
                },
            },
        }
    )
    recovery_task_id = _create_skip_recovery_task(task_id=task_id, context=context_value)
    payload = get_current_task()
    if isinstance(payload, dict):
        payload["recovery_task_id"] = recovery_task_id
    return payload


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


@router.get("/recovery/batch/preview")
def preview_recovery_batch():
    state = rebuild_state()
    recovery_tasks = _pending_recovery_tasks(state)
    previews = [_task_preview_payload(task, state) for task in recovery_tasks]
    return {
        "count": len(previews),
        "tasks": previews,
    }


@router.post("/recovery/batch/apply")
def apply_recovery_batch():
    state = rebuild_state()
    applied = _apply_recovery_batch_updates(state)
    payload = get_current_task()
    if not isinstance(payload, dict):
        payload = {"task": None}
    payload["recovery_batch"] = applied
    return payload


@router.get("/list")
def list_tasks():
    dispatcher = TaskDispatcher()
    dispatch_context = _guardian_dispatch_context()
    state = rebuild_state()
    state = _reschedule_overdue_tasks(
        state,
        dispatcher,
        low_pressure=bool(dispatch_context.get("low_pressure")),
    )
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
