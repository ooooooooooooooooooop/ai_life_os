from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from core.event_sourcing import rebuild_state, append_event
from core.models import UserProfile, Goal, GoalStatus
from core.goal_generator import GoalGenerator
from core.task_decomposer import TaskDecomposer
from core.blueprint import Blueprint

router = APIRouter()

class GenerateFilter(BaseModel):
    n: int = 3

class GenerateResponse(BaseModel):
    candidates: List[dict] # List of Goal dicts
    message: str

class ConfirmRequest(BaseModel):
    goal: dict # Full goal object

@router.post("/generate", response_model=GenerateResponse)
def generate_goals(filter: GenerateFilter):
    state = rebuild_state()
    profile: UserProfile = state["profile"]
    
    if not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")
        
    # Init Engine
    bp = Blueprint()
    # TODO: Pass real LLM when needed, generator uses global get_llm internally
    generator = GoalGenerator(bp)
    
    candidates = generator.generate_candidates(profile, n=filter.n)
    
    # Format for API (Goal object only, ignore score for now or include it)
    # candidates is List[(Goal, Score)]
    result = []
    for goal, score in candidates:
        g_dict = goal.__dict__
        g_dict["_score"] = score.score # inject score for frontend display
        result.append(g_dict)
        
    return GenerateResponse(
        candidates=result,
        message=f"Based on your focus on {profile.focus_area}, here are some suggestions."
    )

@router.post("/confirm")
def confirm_goal(req: ConfirmRequest):
    """
    用户确认目标：
    1. 写入 goal_created 事件
    2. 触发任务分解
    3. 写入 task_created 事件
    """
    # 1. 保存 Goal
    goal_data = req.goal
    # 移除前端注入的临时字段
    if "_score" in goal_data:
        del goal_data["_score"]
        
    # Ensure ID is unique? (LLM might generate collision but low prob)
    # Let's trust LLM or generate new ID here. 
    # For now trust ID.
    
    goal_data["status"] = GoalStatus.ACTIVE
    
    append_event({
        "type": "goal_created",
        "payload": { "goal": goal_data }
    })
    
    # 2. 任务分解
    # 需要重新构建 Goal 对象
    goal = Goal(**goal_data)
    decomposer = TaskDecomposer()
    tasks = decomposer.decompose_goal(goal, start_date=date.today())
    
    created_tasks = []
    for t in tasks:
        append_event({
            "type": "task_created",
            "payload": { "task": t.__dict__ }
        })
        created_tasks.append(t.__dict__)
        
    return {
        "success": True,
        "goal_id": goal.id,
        "tasks_created": len(created_tasks)
    }

@router.get("/list")
def list_goals():
    state = rebuild_state()
    return {
        "active": [g.__dict__ for g in state["goals"] if g.status == GoalStatus.ACTIVE],
        "completed": [g.__dict__ for g in state["goals"] if g.status == GoalStatus.COMPLETED]
    }


class VisionRequest(BaseModel):
    title: str
    description: str = ""
    source: str = "user_input"  # "user_input" / "ai_generated"


@router.post("/vision")
def create_vision(req: VisionRequest):
    """创建愿景级目标"""
    import uuid
    vision_id = f"vision_{uuid.uuid4().hex[:8]}"
    
    goal_data = {
        "id": vision_id,
        "title": req.title,
        "description": req.description,
        "source": req.source,
        "status": GoalStatus.ACTIVE,
        "horizon": "vision",
        "parent_id": None,
        "depends_on": [],
        "tags": []
    }
    
    append_event({
        "type": "goal_created",
        "payload": {"goal": goal_data}
    })
    
    return {"success": True, "vision_id": vision_id}


class DecomposeRequest(BaseModel):
    selected_option: Optional[Dict] = None  #改用 Dict 传递完整选项信息（含标题、描述等）
    custom_input: Optional[str] = None
    context: Optional[Dict[str, Any]] = None # 用户回答的问题上下文


@router.get("/{goal_id}/questions")
def get_decomposition_questions(goal_id: str):
    """获取分解前的评估问题"""
    state = rebuild_state()
    parent_goal = next((g for g in state["goals"] if g.id == goal_id), None)
    
    if not parent_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    from core.goal_generator import GoalGenerator
    bp = Blueprint()
    generator = GoalGenerator(bp)
    
    questions = generator.get_feasibility_questions(parent_goal, state["profile"])
    return {"questions": questions}


@router.post("/{goal_id}/decompose")
def decompose_goal(goal_id: str, req: DecomposeRequest = None):
    """
    AI 分解目标为子目标
    1. 如果只有 context（或无 context 且无 selection），返回候选选项（带概率）
    2. 如果有 selected_option 或 custom_input，创建并保存子目标
    """
    state = rebuild_state()
    
    # 找到目标
    parent_goal = next((g for g in state["goals"] if g.id == goal_id), None)
    if not parent_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # 确定子目标的 horizon
    child_horizon = {
        "vision": "milestone",
        "milestone": "goal",
        "goal": "goal"
    }.get(parent_goal.horizon, "goal")
    
    # 场景 A: 生成选项 (用户回答了问题，或者直接请求分解，且没有做出选择)
    if req is None or (not req.selected_option and not req.custom_input):
        from core.goal_generator import GoalGenerator
        bp = Blueprint()
        generator = GoalGenerator(bp)
        
        context = req.context if req else None
        
        # 获取已存在的子目标标题，避免生成重复内容
        existing_children = [g for g in state["goals"] 
                           if g.parent_id == goal_id and g.status == GoalStatus.ACTIVE]
        existing_titles = [g.title for g in existing_children]
        
        candidates = generator.decompose_to_children(
            parent_goal, 
            state["profile"], 
            n=3,
            context=context,
            existing_titles=existing_titles
        )
        
        return {
            "action": "choose_option",
            "candidates": candidates,
            "horizon": child_horizon
        }

    # 场景 B: 确认选择，创建子目标
    import re
    
    new_title = ""
    new_desc = ""
    
    
    # Aggressive normalization function
    def normalize_title(t):
        # Allow Chinese and English option prefixes
        # Matches: "Option 1:", "选项A -", "Option I.", "选项1:"
        return re.sub(r'^(?:Option|选项)\s*[0-9a-zA-Z一二三四五六七八九十]+[:：\-\.]?\s*', '', t, flags=re.IGNORECASE).strip()

    if req.selected_option:
        raw_title = req.selected_option.get("title", "未命名目标")
        new_title = normalize_title(raw_title)
        new_desc = req.selected_option.get("description", "")
    elif req.custom_input:
        new_title = normalize_title(req.custom_input)
        new_desc = "用户自定义分解目标"
        
    # 查重：检查是否已存在同名活跃子目标
    existing = next((g for g in state["goals"] 
                     if g.parent_id == goal_id 
                     and g.title == new_title 
                     and g.status == GoalStatus.ACTIVE), None)
    
    if existing:
        return {
            "success": True, 
            "goal": existing.__dict__, 
            "tasks_created": 0,
            "message": "目标已存在"
        }
    
    # 生成新 ID
    import uuid
    child_id = f"g_{uuid.uuid4().hex[:8]}"
    
    child_data = {
        "id": child_id,
        "title": new_title,
        "description": new_desc,
        "source": "ai_decompose",
        "status": GoalStatus.ACTIVE,
        "parent_id": goal_id,       # 链接到父目标
        "horizon": child_horizon,   # 下一层级
        "depends_on": [],
        "tags": parent_goal.tags,
        "created_at": datetime.now().isoformat()
    }
    
    # 保存
    append_event({
        "type": "goal_created",
        "payload": {"goal": child_data}
    })
    
    # 如果是最底层 goal，触发任务分解
    if child_horizon == "goal":
        # model Goal is already imported at top level
        child_goal = Goal(**child_data)
        
        # TaskDecomposer is already imported at top level
        # But if we want local import to be safe:
        from core.task_decomposer import TaskDecomposer
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose_goal(child_goal, start_date=date.today())
        
        for t in tasks:
            append_event({
                "type": "task_created",
                "payload": {"task": t.__dict__}
            })
        
        return {
            "success": True,
            "goal": child_data,
            "tasks_created": len(tasks)
        }
    
    return {"success": True, "goal": child_data}


@router.delete("/{goal_id}")
def delete_goal(goal_id: str):
    """删除（放弃）目标"""
    state = rebuild_state()
    goal = next((g for g in state["goals"] if g.id == goal_id), None)
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    append_event({
        "type": "goal_updated",
        "payload": {"id": goal_id, "status": GoalStatus.ABANDONED}
    })
    
    return {"success": True}


@router.get("/tree")
def get_goal_tree():
    """获取目标树形结构"""
    state = rebuild_state()
    goals = state["goals"]
    
    # 构建树
    def build_tree(parent_id: Optional[str] = None):
        children = []
        for g in goals:
            if g.parent_id == parent_id and g.status == GoalStatus.ACTIVE:
                node = g.__dict__.copy()
                node["children"] = build_tree(g.id)
                children.append(node)
        return children
    
    return {"tree": build_tree(None)}
