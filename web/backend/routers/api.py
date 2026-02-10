from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import json
import asyncio
from datetime import datetime
from dataclasses import asdict

from core.steward import Steward
from core.snapshot_manager import restore_from_snapshot, create_snapshot
from core.objective_engine.registry import GoalRegistry
from core.objective_engine.models import GoalState, GoalLayer, ObjectiveNode
from core.event_sourcing import append_event, EVENT_LOG_PATH
from core.feedback_classifier import classify_feedback, FeedbackIntent
from core.interaction_handler import InteractionHandler
from core.retrospective import build_guardian_retrospective_response
from scheduler.daily_tick import ensure_tick_applied

router = APIRouter()


# ============ Pydantic Models ============

class VisionUpdateRequest(BaseModel):
    """Vision 更新请求"""
    title: Optional[str] = None
    description: Optional[str] = None


class FeedbackRequest(BaseModel):
    """自由文本反馈请求"""
    message: str

class InteractionRequest(BaseModel):
    """通用自然语言交互请求"""
    message: str


# ============ Helper ============

def get_steward() -> Steward:
    """Helper to instantiate Steward with fresh state (on-demand tick applied)."""
    state = ensure_tick_applied()
    registry = GoalRegistry()
    return Steward(state, registry)


# ============ State API ============

def _has_review_due_this_week() -> bool:
    """True if event log contains review_due in the current week."""
    from datetime import datetime, timedelta
    if not EVENT_LOG_PATH.exists():
        return False
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
                if ev.get("type") != "review_due":
                    continue
                d = ev.get("date") or (ev.get("timestamp", "")[:10] if ev.get("timestamp") else "")
                if not d:
                    continue
                event_date = datetime.strptime(d[:10], "%Y-%m-%d").date()
                if week_start <= event_date <= week_end:
                    return True
            except (json.JSONDecodeError, ValueError):
                continue
    return False


@router.get("/state")
async def get_state():
    """Get the full system state for the UI."""
    steward = get_steward()
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
            if str(getattr(getattr(t, "status", None), "value", getattr(t, "status", ""))) == "pending"
        ]

    response = {
        "identity": identity,
        "metrics": system_state.get("rhythm") or {},
        "energy_phase": steward.get_current_phase(),
        "active_tasks": active_tasks,
        "visions": [asdict(v) for v in registry.visions],
        "objectives": [asdict(o) for o in registry.objectives],
        "goals": [asdict(g) for g in registry.goals],
        "pending_confirmation": [
            asdict(g) for g in registry.goals + registry.objectives
            if g.state == GoalState.VISION_PENDING_CONFIRMATION
        ],
        "system_health": {
            "status": "nominal", 
            "queue_load": len(active_tasks)
        },
        "weekly_review_due": _has_review_due_this_week(),
    }
    return response


# ============ Guardian Retrospective API ============

@router.get("/retrospective")
async def get_retrospective(days: int = 7):
    """Guardian 复盘：派生视图，只读 event_log。返回 period、rhythm、alignment、friction、observations 及 intervention_level、suggestion、display、require_confirm。"""
    return build_guardian_retrospective_response(days)


# ============ Vision API ============

@router.get("/visions")
async def list_visions():
    """获取所有 Vision"""
    registry = GoalRegistry()
    return {"visions": [asdict(v) for v in registry.visions]}


@router.put("/visions/{vision_id}")
async def update_vision(vision_id: str, request: VisionUpdateRequest):
    """更新 Vision（触发 Steward 重新推导）"""
    registry = GoalRegistry()
    vision = registry.get_node(vision_id)
    
    if not vision:
        raise HTTPException(status_code=404, detail="Vision not found")
    
    if vision.layer != GoalLayer.VISION:
        raise HTTPException(status_code=400, detail="Node is not a Vision")
    
    # 更新字段
    if request.title:
        vision.title = request.title
    if request.description:
        vision.description = request.description
    vision.updated_at = datetime.now().isoformat()
    
    registry.update_node(vision)
    
    # 记录事件
    append_event({
        "type": "vision_updated",
        "vision_id": vision_id,
        "timestamp": datetime.now().isoformat(),
        "payload": {"title": vision.title}
    })
    
    # TODO: 触发 Steward 重新推导（后续实现）
    
    return {"status": "success", "vision": asdict(vision)}


# ============ Goal 确认/拒绝 API ============

@router.post("/goals/{goal_id}/confirm")
async def confirm_goal(goal_id: str):
    """确认 Steward 推导的目标，激活它"""
    registry = GoalRegistry()
    goal = registry.get_node(goal_id)
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # 仅允许确认待确认状态的目标
    if goal.state != GoalState.VISION_PENDING_CONFIRMATION:
        raise HTTPException(
            status_code=400, 
            detail=f"Goal is not pending confirmation (current: {goal.state.value})"
        )
    
    goal.state = GoalState.ACTIVE
    goal.updated_at = datetime.now().isoformat()
    registry.update_node(goal)
    
    append_event({
        "type": "goal_confirmed",
        "goal_id": goal_id,
        "timestamp": datetime.now().isoformat()
    })
    
    return {"status": "confirmed", "goal_id": goal_id}


@router.post("/goals/{goal_id}/reject")
async def reject_goal(goal_id: str):
    """拒绝 Steward 推导的目标，归档它"""
    registry = GoalRegistry()
    goal = registry.get_node(goal_id)
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    goal.state = GoalState.ARCHIVED
    goal.updated_at = datetime.now().isoformat()
    registry.update_node(goal)
    
    append_event({
        "type": "goal_rejected",
        "goal_id": goal_id,
        "timestamp": datetime.now().isoformat()
    })
    
    return {"status": "rejected", "goal_id": goal_id}


# ============ 自由文本反馈 API ============

@router.post("/goals/{goal_id}/feedback")
async def submit_feedback(goal_id: str, request: FeedbackRequest):
    """
    接收自由文本反馈，自动识别意图并更新目标状态。
    
    支持意图: complete, skip, defer, partial, blocked
    """
    registry = GoalRegistry()
    goal = registry.get_node(goal_id)
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # LLM 分类
    result = classify_feedback(request.message)
    
    # 根据意图更新状态
    new_state = goal.state
    if result.intent == FeedbackIntent.COMPLETE:
        new_state = GoalState.COMPLETED
        goal.success_count += 1
    elif result.intent == FeedbackIntent.SKIP:
        goal.skip_count += 1
        # 保持 ACTIVE，但记录 skip
    elif result.intent == FeedbackIntent.DEFER:
        # 保持 ACTIVE，记录 defer 原因
        pass
    elif result.intent == FeedbackIntent.BLOCKED:
        new_state = GoalState.BLOCKED
        goal.blocked_reason = result.extracted_reason
    elif result.intent == FeedbackIntent.PARTIAL:
        # 保持 ACTIVE，可更新进度
        pass
    
    goal.state = new_state
    goal.updated_at = datetime.now().isoformat()
    registry.update_node(goal)
    
    # 记录事件
    append_event({
        "type": "goal_feedback",
        "goal_id": goal_id,
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "message": request.message,
            "progress_percent": result.progress_percent
        }
    })
    
    return {
        "status": "success",
        "goal_id": goal_id,
        "detected_intent": result.intent.value,
        "confidence": result.confidence,
        "new_state": new_state.value
    }


class ActionRequest(BaseModel):
    """Explicit UI Action Request"""
    action: str  # complete, skip, start
    reason: Optional[str] = None


@router.post("/goals/{goal_id}/action")
async def execute_action(goal_id: str, request: ActionRequest):
    """
    Explicit action handler for UI buttons (Complete/Skip/Start).
    Bypasses LLM classification for deterministic behavior.
    """
    registry = GoalRegistry()
    goal = registry.get_node(goal_id)

    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    new_state = goal.state
    action_type = request.action.lower()

    if action_type == "complete":
        new_state = GoalState.COMPLETED
        goal.success_count += 1
    elif action_type == "skip":
        # Keep ACTIVE but record skip
        goal.skip_count += 1
    elif action_type == "start":
        # Just log start event, state remains/becomes ACTIVE
        new_state = GoalState.ACTIVE

    goal.state = new_state
    goal.updated_at = datetime.now().isoformat()
    registry.update_node(goal)

    # Append Event
    append_event({
        "type": "goal_action",
        "goal_id": goal_id,
        "timestamp": datetime.now().isoformat(),
        "payload": {"action": action_type, "reason": request.reason}
    })
    
    # If completed, we should also trigger the generic completed event for consistency
    if new_state == GoalState.COMPLETED:
         append_event({
            "type": "goal_completed",
            "goal_id": goal_id,
            "timestamp": datetime.now().isoformat()
        })

    return {"status": "success", "goal_id": goal_id, "new_state": new_state.value}


@router.get("/timeline")
async def get_timeline():
    """
    Get the daily timeline/schedule.
    Currently generated from Active Goals + Steward's current plan.
    """
    steward = get_steward()
    # In a real implementation, Steward might have a 'schedule' object.
    # For now, we simulate a timeline based on active actions.
    
    # We pull active goals
    sys_state = steward.state
    active_tasks = sys_state.get("ongoing", {}).get("active_tasks", [])
    
    # We can also look at registry goals that are active
    registry_goals = [g for g in steward.registry.goals if g.state == GoalState.ACTIVE]
    
    timeline_items = []
    
    # Mock timeline construction
    # Ideally this comes from a Scheduler module
    current_hour = datetime.now().hour
    
    for i, goal in enumerate(registry_goals):
        start_time = f"{current_hour + i}:00"
        end_time = f"{current_hour + i + 1}:00"
        timeline_items.append({
            "id": goal.id,
            "title": goal.title,
            "start": start_time,
            "end": end_time,
            "type": "goal",
            "status": "scheduled"
        })
        
    return {"timeline": timeline_items}



# ============ 目标列表 API ============

@router.get("/goals")
async def list_goals(
    state: Optional[str] = None,
    layer: Optional[str] = None
):
    """获取目标列表，支持筛选"""
    registry = GoalRegistry()
    
    # 合并所有目标
    all_goals = registry.visions + registry.objectives + registry.goals
    
    # 筛选
    if state:
        all_goals = [g for g in all_goals if g.state.value == state]
    if layer:
        all_goals = [g for g in all_goals if g.layer.value == layer]
    
    return {"goals": [asdict(g) for g in all_goals], "count": len(all_goals)}


# ============ SSE Events ============

@router.get("/events")
async def stream_events():
    """SSE endpoint for real-time system events."""
    async def event_generator():
        if not EVENT_LOG_PATH.exists():
            yield "data: {\"type\": \"system\", \"message\": \"No logs found\"}\n\n"
            return

        with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            # Read last 10 lines for context
            lines = f.readlines()
            for line in lines[-10:]:
                yield f"data: {line}\n\n"
                
            # Then tail
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
    """
    手动触发 Steward 思考循环 (Debug/Demo Mode)。
    执行完整循环：推断目标 -> 生成计划 -> 执行自动维护任务。
    """
    steward = get_steward()
    plan = steward.run_planning_cycle()
    
    return {
        "status": "cycled", 
        "generated_actions": plan.get("actions", []),
        "executed_auto_tasks": plan.get("executed_auto_tasks", []),
        "audit": plan.get("audit", {})
    }


@router.post("/interact")
async def interact(request: InteractionRequest):
    """
    通用自然语言交互接口 (The Mouth).
    处理: 身份录入、目标反馈、闲聊
    """
    steward = get_steward()
    handler = InteractionHandler(steward.registry, steward.state)
    
    result = handler.process(request.message)
    
    # 状态持久化 (Event Sourcing)
    if result.action_type == "UPDATE_IDENTITY":
        # 记录 Identity 变更事件
        append_event({
            "type": "identity_updated",
            "timestamp": datetime.now().isoformat(),
            "payload": result.updates
        })
        # 这里为了简化，我们假设下次 get_steward() 会 rebuild
        # FIX: 立即强制更新快照，确保 Steward 看到最新状态
        create_snapshot(force=True)
        
    elif result.action_type == "GOAL_FEEDBACK":
        # Handler 已经调用了 registry.update_node()，这会保存 goal_registry.json
        # 但我们需要记录 Event 以便回溯
        for goal_id, status in result.updates.items():
            append_event({
                "type": "goal_feedback",
                "goal_id": goal_id,
                "timestamp": datetime.now().isoformat(),
                "payload": {
                    "intent": status,
                    "message": request.message,
                    "source": "nlp_interaction"
                }
            })

    return {
        "response": result.response_text,
        "action_type": result.action_type,
        "updated_fields": result.updated_fields
    }
