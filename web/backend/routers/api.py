import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.event_sourcing import EVENT_LOG_PATH, append_event
from core.feedback_classifier import classify_feedback
from core.goal_service import GoalService
from core.interaction_handler import InteractionHandler
from core.objective_engine.models import GoalState
from core.objective_engine.registry import GoalRegistry
from core.retrospective import build_guardian_retrospective_response
from core.snapshot_manager import create_snapshot
from core.steward import Steward
from scheduler.daily_tick import ensure_tick_applied

router = APIRouter()


class VisionUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class FeedbackRequest(BaseModel):
    message: str


class InteractionRequest(BaseModel):
    message: str


class ActionRequest(BaseModel):
    action: str  # complete, skip, start
    reason: Optional[str] = None


def get_steward() -> Steward:
    state = ensure_tick_applied()
    registry = GoalRegistry()
    return Steward(state, registry)


def get_goal_service() -> GoalService:
    return GoalService()


def _has_review_due_this_week() -> bool:
    if not EVENT_LOG_PATH.exists():
        return False
    from datetime import timedelta

    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("type") != "review_due":
                    continue
                timestamp = event.get("timestamp") or ""
                date_raw = event.get("date") or timestamp[:10]
                if not date_raw:
                    continue
                event_date = datetime.strptime(date_raw[:10], "%Y-%m-%d").date()
                if week_start <= event_date <= week_end:
                    return True
            except (json.JSONDecodeError, ValueError):
                continue
    return False


@router.get("/state")
async def get_state():
    steward = get_steward()
    service = get_goal_service()
    system_state = steward.state
    registry = steward.registry

    identity = system_state.get("identity")
    if not identity and system_state.get("profile") is not None:
        profile = system_state["profile"]
        identity = dict(profile if isinstance(profile, dict) else profile.__dict__)

    active_tasks = system_state.get("ongoing", {}).get("active_tasks")
    if active_tasks is None:
        tasks = system_state.get("tasks", [])
        active_tasks = [
            asdict(t)
            for t in tasks
            if str(
                getattr(getattr(t, "status", None), "value", getattr(t, "status", ""))
            )
            == "pending"
        ]

    return {
        "identity": identity,
        "metrics": system_state.get("rhythm") or {},
        "energy_phase": steward.get_current_phase(),
        "active_tasks": active_tasks,
        "visions": [service.node_to_dict(v, include_legacy=True) for v in registry.visions],
        "objectives": [service.node_to_dict(o, include_legacy=True) for o in registry.objectives],
        "goals": [service.node_to_dict(g, include_legacy=True) for g in registry.goals],
        "pending_confirmation": [
            service.node_to_dict(g, include_legacy=True)
            for g in (registry.objectives + registry.goals)
            if g.state == GoalState.VISION_PENDING_CONFIRMATION
        ],
        "system_health": {
            "status": "nominal",
            "queue_load": len(active_tasks),
        },
        "weekly_review_due": _has_review_due_this_week(),
    }


@router.get("/retrospective")
async def get_retrospective(days: int = 7):
    return build_guardian_retrospective_response(days)


@router.get("/visions")
async def list_visions():
    service = get_goal_service()
    return {
        "visions": [
            service.node_to_dict(v, include_legacy=True) for v in service.list_visions()
        ]
    }


@router.put("/visions/{vision_id}")
async def update_vision(vision_id: str, request: VisionUpdateRequest):
    service = get_goal_service()
    try:
        vision = service.update_vision(
            vision_id,
            title=request.title,
            description=request.description,
        )
    except ValueError as exc:
        message = str(exc).lower()
        if "not found" in message:
            raise HTTPException(status_code=404, detail="Vision not found")
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "vision": service.node_to_dict(vision, include_legacy=True)}


@router.post("/goals/{goal_id}/confirm")
async def confirm_goal(goal_id: str):
    service = get_goal_service()
    try:
        service.confirm_goal(goal_id, strict_pending=True)
    except ValueError as exc:
        message = str(exc).lower()
        if "not found" in message:
            raise HTTPException(status_code=404, detail="Goal not found")
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "confirmed", "goal_id": goal_id}


@router.post("/goals/{goal_id}/reject")
async def reject_goal(goal_id: str):
    service = get_goal_service()
    try:
        service.reject_goal(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "rejected", "goal_id": goal_id}


@router.post("/goals/{goal_id}/feedback")
async def submit_feedback(goal_id: str, request: FeedbackRequest):
    result = classify_feedback(request.message)
    service = get_goal_service()
    try:
        goal = service.apply_feedback(
            goal_id,
            result.intent.value,
            extracted_reason=result.extracted_reason,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")

    append_event(
        {
            "type": "goal_feedback",
            "goal_id": goal_id,
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "intent": result.intent.value,
                "confidence": result.confidence,
                "message": request.message,
                "progress_percent": result.progress_percent,
            },
        }
    )

    return {
        "status": "success",
        "goal_id": goal_id,
        "detected_intent": result.intent.value,
        "confidence": result.confidence,
        "new_state": goal.state.value,
    }


@router.post("/goals/{goal_id}/action")
async def execute_action(goal_id: str, request: ActionRequest):
    service = get_goal_service()
    action_type = request.action.lower()

    try:
        goal = service.apply_action(goal_id, action_type, reason=request.reason)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")

    append_event(
        {
            "type": "goal_action",
            "goal_id": goal_id,
            "timestamp": datetime.now().isoformat(),
            "payload": {"action": action_type, "reason": request.reason},
        }
    )

    if goal.state == GoalState.COMPLETED:
        append_event(
            {
                "type": "goal_completed",
                "goal_id": goal_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

    return {"status": "success", "goal_id": goal_id, "new_state": goal.state.value}


@router.get("/timeline")
async def get_timeline():
    steward = get_steward()
    registry_goals = [g for g in steward.registry.goals if g.state == GoalState.ACTIVE]

    timeline_items = []
    current_hour = datetime.now().hour
    for idx, goal in enumerate(registry_goals):
        timeline_items.append(
            {
                "id": goal.id,
                "title": goal.title,
                "start": f"{current_hour + idx}:00",
                "end": f"{current_hour + idx + 1}:00",
                "type": "goal",
                "status": "scheduled",
            }
        )
    return {"timeline": timeline_items}


@router.get("/goals")
async def list_goals(state: Optional[str] = None, layer: Optional[str] = None):
    service = get_goal_service()
    all_goals = service.list_nodes(state=state, layer=layer)
    return {
        "goals": [service.node_to_dict(g, include_legacy=True) for g in all_goals],
        "count": len(all_goals),
    }


@router.get("/events")
async def stream_events():
    async def event_generator():
        if not EVENT_LOG_PATH.exists():
            yield "data: {\"type\": \"system\", \"message\": \"No logs found\"}\n\n"
            return

        with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-10:]:
                yield f"data: {line}\n\n"

            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sys/cycle")
async def trigger_cycle():
    steward = get_steward()
    plan = steward.run_planning_cycle()
    return {
        "status": "cycled",
        "generated_actions": plan.get("actions", []),
        "executed_auto_tasks": plan.get("executed_auto_tasks", []),
        "audit": plan.get("audit", {}),
    }


@router.post("/interact")
async def interact(request: InteractionRequest):
    steward = get_steward()
    handler = InteractionHandler(steward.registry, steward.state)
    result = handler.process(request.message)

    if result.action_type == "UPDATE_IDENTITY":
        append_event(
            {
                "type": "identity_updated",
                "timestamp": datetime.now().isoformat(),
                "payload": result.updates,
            }
        )
        create_snapshot(force=True)
    elif result.action_type == "GOAL_FEEDBACK":
        for goal_id, status in result.updates.items():
            append_event(
                {
                    "type": "goal_feedback",
                    "goal_id": goal_id,
                    "timestamp": datetime.now().isoformat(),
                    "payload": {
                        "intent": status,
                        "message": request.message,
                        "source": "nlp_interaction",
                    },
                }
            )

    return {
        "response": result.response_text,
        "action_type": result.action_type,
        "updated_fields": result.updated_fields,
    }
