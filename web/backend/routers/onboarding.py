from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from core.event_sourcing import rebuild_state, append_event
from core.models import UserProfile

router = APIRouter()

class OnboardRequest(BaseModel):
    answer: str

class Question(BaseModel):
    id: str
    text: str
    options: Optional[List[str]] = None
    placeholder: Optional[str] = None

class OnboardStatus(BaseModel):
    completed: bool
    profile: Optional[dict] = None
    next_question: Optional[Question] = None

# 定义问题流
QUESTIONS = [
    Question(id="occupation", text="你目前主要的身分或职业是什么？", placeholder="例如：软件工程师、学生..."),
    Question(id="focus_area", text="近期你最想提升或关注的领域是？", placeholder="例如：React 开发、身体健康、英语口语..."),
    Question(id="daily_hours", text="除工作/学习外，你每天大约有多少小时可自由支配？", placeholder="例如：2h, 30min")
]

@router.get("/status", response_model=OnboardStatus)
def get_status():
    state = rebuild_state()
    profile: UserProfile = state["profile"]
    
    if profile.onboarding_completed:
        return OnboardStatus(completed=True, profile=profile.__dict__)
    
    # 找到第一个未回答的问题
    # 简单的逻辑：检查 profile 字段是否为空
    next_q = None
    if not profile.occupation:
        next_q = QUESTIONS[0]
    elif not profile.focus_area:
        next_q = QUESTIONS[1]
    elif not profile.daily_hours:
        next_q = QUESTIONS[2]
    else:
        # 所有字段都有了，但 onboarding_completed 为 False
        # 说明刚好答完，需要触发完成事件
        append_event({
            "type": "onboarding_completed",
        })
        return OnboardStatus(completed=True, profile=profile.__dict__)
        
    return OnboardStatus(completed=False, next_question=next_q)

@router.post("/answer")
def submit_answer(request: OnboardRequest):
    # 1. 获取当前状态
    state = rebuild_state()
    profile: UserProfile = state["profile"]
    
    # 2. 确定当前在回答哪个问题
    field = None
    if not profile.occupation:
        field = "occupation"
    elif not profile.focus_area:
        field = "focus_area"
    elif not profile.daily_hours:
        field = "daily_hours"
    else:
        return get_status() # 已完成
        
    # 3. 记录事件
    append_event({
        "type": "profile_updated",
        "payload": {
            "field": field,
            "value": request.answer
        }
    })
    
    return get_status()
