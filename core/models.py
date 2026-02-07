"""
Core Data Models for AI Life OS.
Defines the fundamental data structures for users, goals, tasks, and history.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict
from enum import Enum

class GoalStatus(str, Enum):
    PENDING_CONFIRM = "pending_confirm"  # 待用户确认
    ACTIVE = "active"                    # 进行中
    COMPLETED = "completed"              # 已完成
    ABANDONED = "abandoned"              # 已放弃

class TaskStatus(str, Enum):
    PENDING = "pending"      # 待执行
    COMPLETED = "completed"  # 已完成
    SKIPPED = "skipped"      # 已跳过
    EXPIRED = "expired"      # 已过期（超 1 天无反馈）

@dataclass
class UserProfile:
    """用户画像（动态学习）"""
    occupation: str = ""           # 职业
    focus_area: str = ""           # 关注方向
    daily_hours: str = ""          # 每日可用时间 (e.g., "3h")
    peak_hours: List[int] = field(default_factory=list)   # 高效时段 (e.g., [9, 10, 11])
    preferences: Dict = field(default_factory=dict)       # 偏好
    onboarding_completed: bool = False

@dataclass
class Goal:
    """目标（支持层级结构：vision → milestone → goal）"""
    id: str
    title: str
    description: str
    source: str                    # "ai_generated" / "user_input"
    status: GoalStatus
    # 层级相关字段
    parent_id: Optional[str] = None         # 父目标 ID（形成树结构）
    horizon: str = "goal"                   # "vision" / "milestone" / "goal"
    depends_on: List[str] = field(default_factory=list)  # 依赖的其他目标 ID
    # 原有字段
    resource_description: str = "" # 资源描述
    target_level: str = ""         # 目标程度
    deadline: Optional[date] = None
    tags: List[str] = field(default_factory=list) # e.g. ["Career", "Health"]
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class Task:
    """任务（从目标分解）"""
    id: str
    goal_id: str
    description: str               # 具体描述
    scheduled_date: date
    scheduled_time: Optional[str] = None  # "09:00"
    estimated_minutes: int = 30
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    skip_reason: str = ""

@dataclass
class Execution:
    """执行记录"""
    id: str
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    outcome: str = ""              # "completed" / "skipped" / "feedback"
    feedback_type: str = ""        # "not_suitable" / "no_energy" / ...
    progress_note: str = ""        # 用户输入的进度
