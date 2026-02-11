import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.blueprint_anchor import AnchorManager
from core.event_sourcing import EVENT_LOG_PATH, EVENT_SCHEMA_VERSION, append_event
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


class RetrospectiveConfirmRequest(BaseModel):
    days: int = 7
    fingerprint: Optional[str] = None
    note: Optional[str] = None


class AnchorActivateRequest(BaseModel):
    force: bool = False


def get_steward() -> Steward:
    state = ensure_tick_applied()
    registry = GoalRegistry()
    return Steward(state, registry)


def get_goal_service() -> GoalService:
    return GoalService()


BLUEPRINT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "concepts"
    / "better_human_blueprint.md"
)


def _anchor_payload(anchor) -> dict:
    if not anchor:
        return {
            "active": False,
            "version": None,
            "created_at": None,
            "confirmed_by_user": False,
            "non_negotiables_count": 0,
            "commitments_count": 0,
            "anti_values_count": 0,
            "instinct_adversaries_count": 0,
        }
    return {
        "active": True,
        "version": anchor.version,
        "created_at": anchor.created_at,
        "confirmed_by_user": bool(anchor.confirmed_by_user),
        "non_negotiables_count": len(anchor.non_negotiables or ()),
        "commitments_count": len(anchor.long_horizon_commitments or ()),
        "anti_values_count": len(anchor.anti_values or ()),
        "instinct_adversaries_count": len(anchor.instinct_adversaries or ()),
    }


def _anchor_diff_payload(diff) -> dict:
    return {
        "status": diff.status,
        "version_change": diff.version_change,
        "added_non_negotiables": sorted(list(diff.added_non_negotiables or set())),
        "removed_non_negotiables": sorted(list(diff.removed_non_negotiables or set())),
        "added_commitments": sorted(list(diff.added_commitments or set())),
        "removed_commitments": sorted(list(diff.removed_commitments or set())),
        "added_anti_values": sorted(list(diff.added_anti_values or set())),
        "removed_anti_values": sorted(list(diff.removed_anti_values or set())),
        "added_adversaries": sorted(list(diff.added_adversaries or set())),
        "removed_adversaries": sorted(list(diff.removed_adversaries or set())),
    }


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


def _normalized_audit(
    raw_audit: Optional[dict],
    default_strategy: str,
    default_trigger: str,
    default_constraint: str = "",
    default_risk: str = "",
) -> dict:
    audit = raw_audit if isinstance(raw_audit, dict) else {}
    decision_reason = audit.get("decision_reason", {})
    if not isinstance(decision_reason, dict):
        decision_reason = {}

    used_state_fields = audit.get("used_state_fields", [])
    if not isinstance(used_state_fields, list):
        used_state_fields = []

    normalized = {
        "strategy": audit.get("strategy") or default_strategy,
        "used_state_fields": used_state_fields,
        "decision_reason": {
            "trigger": decision_reason.get("trigger") or default_trigger,
            "constraint": decision_reason.get("constraint") or default_constraint,
            "risk": decision_reason.get("risk") or default_risk,
        },
    }
    # Preserve extension fields used by planner-level guards (e.g., Anchor).
    for extra_key in ("anchor",):
        if extra_key in audit:
            normalized[extra_key] = audit.get(extra_key)
    return normalized


@router.get("/state")
async def get_state():
    steward = get_steward()
    service = get_goal_service()
    system_state = steward.state
    registry = steward.registry

    identity = system_state.get("identity") or {}
    active_tasks = [
        task.__dict__
        for task in system_state.get("tasks", [])
        if str(getattr(task.status, "value", task.status)) == "pending"
    ]

    state_audit = _normalized_audit(
        raw_audit={
            "strategy": "state_projection",
            "used_state_fields": [
                "identity",
                "rhythm",
                "tasks",
                "goal_registry",
                "event_log.review_due",
                "anchor.current",
                "retrospective.alignment.trend",
            ],
            "decision_reason": {
                "trigger": "State requested by API client",
                "constraint": "Read-model projection only",
                "risk": "Stale reads if filesystem is modified externally",
            },
        },
        default_strategy="state_projection",
        default_trigger="State requested by API client",
    )
    retrospective = build_guardian_retrospective_response(days=7)
    guardian_state = system_state.get("guardian") or {}
    alignment_summary = service.summarize_alignment(registry.objectives + registry.goals)
    alignment_trend = (retrospective.get("alignment") or {}).get("trend", {})
    anchor_snapshot = _anchor_payload(None)
    try:
        anchor = AnchorManager().get_current()
        if anchor:
            anchor_snapshot = _anchor_payload(anchor)
    except Exception:
        pass

    return {
        "identity": identity,
        "metrics": system_state.get("rhythm") or {},
        "energy_phase": steward.get_current_phase(),
        "active_tasks": active_tasks,
        "visions": [service.node_to_dict(v) for v in registry.visions],
        "objectives": [service.node_to_dict(o) for o in registry.objectives],
        "goals": [service.node_to_dict(g) for g in registry.goals],
        "pending_confirmation": [
            service.node_to_dict(g)
            for g in (registry.objectives + registry.goals)
            if g.state == GoalState.VISION_PENDING_CONFIRMATION
        ],
        "system_health": {
            "status": "nominal",
            "queue_load": len(active_tasks),
        },
        "weekly_review_due": _has_review_due_this_week(),
        "anchor": anchor_snapshot,
        "alignment": {
            "goal_summary": alignment_summary,
            "weekly_trend": alignment_trend,
        },
        "guardian": {
            "intervention_level": retrospective.get("intervention_level"),
            "pending_confirmation": bool(retrospective.get("require_confirm")),
            "confirmation_action": retrospective.get("confirmation_action", {}),
            "last_intervention_confirmation": guardian_state.get(
                "last_intervention_confirmation"
            ),
        },
        "audit": state_audit,
        "meta": {
            "event_schema_version": EVENT_SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(),
        },
    }


@router.get("/retrospective")
async def get_retrospective(days: int = 7):
    return build_guardian_retrospective_response(days)


@router.post("/retrospective/confirm")
async def confirm_retrospective_intervention(request: RetrospectiveConfirmRequest):
    days = request.days or 7
    current_payload = build_guardian_retrospective_response(days)
    action = current_payload.get("confirmation_action") or {}
    current_fingerprint = action.get("fingerprint")

    if request.fingerprint and current_fingerprint and request.fingerprint != current_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Intervention context changed, refresh retrospective before confirming",
        )

    if not action.get("required"):
        return {
            "status": "noop",
            "reason": "confirmation_not_required",
            "retrospective": current_payload,
        }

    if action.get("confirmed"):
        return {"status": "already_confirmed", "retrospective": current_payload}

    append_event(
        {
            "type": "guardian_intervention_confirmed",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "days": days,
                "fingerprint": current_fingerprint,
                "suggestion": current_payload.get("suggestion", ""),
                "signals": [
                    source.get("signal")
                    for source in current_payload.get("suggestion_sources", [])
                ],
                "note": request.note or "",
            },
        }
    )

    updated_payload = build_guardian_retrospective_response(days)
    return {"status": "confirmed", "retrospective": updated_payload}


@router.get("/anchor/current")
async def get_anchor_current():
    try:
        anchor = AnchorManager().get_current()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load anchor: {exc}")
    return {
        "blueprint_path": str(BLUEPRINT_PATH),
        "anchor": _anchor_payload(anchor),
    }


@router.get("/anchor/diff")
async def get_anchor_diff():
    if not BLUEPRINT_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Blueprint file not found: {BLUEPRINT_PATH}")

    manager = AnchorManager()
    current = manager.get_current()
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
        diff = manager.diff(current, draft)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate anchor diff: {exc}")

    return {
        "blueprint_path": str(BLUEPRINT_PATH),
        "current": _anchor_payload(current),
        "draft": _anchor_payload(draft),
        "diff": _anchor_diff_payload(diff),
    }


@router.post("/anchor/activate")
async def activate_anchor(request: AnchorActivateRequest):
    if not BLUEPRINT_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Blueprint file not found: {BLUEPRINT_PATH}")

    manager = AnchorManager()
    current = manager.get_current()
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
        diff = manager.diff(current, draft)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate anchor draft: {exc}")

    if current and diff.status == "unchanged" and not request.force:
        return {
            "status": "noop",
            "reason": "anchor_unchanged",
            "current": _anchor_payload(current),
            "diff": _anchor_diff_payload(diff),
        }

    try:
        activated = manager.activate(draft)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to activate anchor: {exc}")

    append_event(
        {
            "type": "anchor_activated",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "version": activated.version,
                "source_hash": activated.source_hash,
                "blueprint_path": str(BLUEPRINT_PATH),
            },
        }
    )

    return {
        "status": "activated",
        "anchor": _anchor_payload(activated),
        "diff": _anchor_diff_payload(diff),
    }


@router.get("/visions")
async def list_visions():
    service = get_goal_service()
    return {"visions": [service.node_to_dict(v) for v in service.list_visions()]}


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
    return {"status": "success", "vision": service.node_to_dict(vision)}


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
        "goals": [service.node_to_dict(g) for g in all_goals],
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
    audit = _normalized_audit(
        raw_audit=plan.get("audit", {}),
        default_strategy="planning_cycle",
        default_trigger="Manual cycle trigger",
        default_constraint="Daily planning bounds",
        default_risk="Over-allocation or stale context",
    )
    return {
        "status": "cycled",
        "generated_actions": plan.get("actions", []),
        "executed_auto_tasks": plan.get("executed_auto_tasks", []),
        "audit": audit,
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
