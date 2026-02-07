from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

from core.event_sourcing import rebuild_state, append_event
from core.models import Task, TaskStatus
from core.task_dispatcher import TaskDispatcher

router = APIRouter()

class ActionRequest(BaseModel):
    reason: Optional[str] = None
    feedback_type: Optional[str] = None

class ProgressRequest(BaseModel):
    message: str # "我看了 15 分钟"

@router.get("/current")
def get_current_task():
    state = rebuild_state()
    dispatcher = TaskDispatcher()
    
    current_task = dispatcher.get_current_task(state["tasks"])
    
    if not current_task:
        return {"task": None, "reason": "No pending tasks or all scheduled for future"}
        
    # Find associated goal title
    goal_title = "Unknown Goal"
    for g in state["goals"]:
        if g.id == current_task.goal_id:
            goal_title = g.title
            break
            
    result = current_task.__dict__
    result["goal_title"] = goal_title
    
    return {"task": result}

@router.post("/{task_id}/complete")
def complete_task(task_id: str):
    append_event({
        "type": "task_updated",
        "payload": {
            "id": task_id,
            "updates": {
                "status": TaskStatus.COMPLETED,
                "completed_at": datetime.now().isoformat()
            }
        }
    })
    
    # 记录执行
    append_event({
        "type": "execution_completed",
        "payload": {
            "id": f"exec_{task_id}_{int(datetime.now().timestamp())}", # Temporary ID logic
            "outcome": "completed",
            "completed_at": datetime.now().isoformat()
        }
    })
    
    return get_current_task()

@router.post("/{task_id}/skip")
def skip_task(task_id: str, req: ActionRequest):
    append_event({
        "type": "task_updated",
        "payload": {
            "id": task_id,
            "updates": {
                "status": TaskStatus.SKIPPED,
                "skip_reason": req.reason or "skipped_by_user"
            }
        }
    })
    return get_current_task()

@router.post("/progress")
def update_progress(req: ProgressRequest):
    # 简单记录进度事件
    append_event({
        "type": "progress_updated",
        "payload": {
            "message": req.message,
            "raw_text": req.message
        }
    })
    return {"status": "recorded", "message": "Progress logged"}

@router.get("/list")
def list_tasks():
    """获取所有任务列表（按状态分组）"""
    state = rebuild_state()
    tasks = state.get("tasks", [])
    
    pending = []
    completed = []
    
    for t in tasks:
        task_dict = t.__dict__.copy()
        # 添加关联的目标标题
        for g in state.get("goals", []):
            if g.id == t.goal_id:
                task_dict["goal_title"] = g.title
                break
        
        if t.status == TaskStatus.PENDING:
            pending.append(task_dict)
        elif t.status == TaskStatus.COMPLETED:
            completed.append(task_dict)
    
    return {
        "pending": pending,
        "completed": completed,
        "total": len(tasks)
    }

