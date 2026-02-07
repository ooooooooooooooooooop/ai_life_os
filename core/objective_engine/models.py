"""
Objective Engine models: Vision / Objective / Goal hierarchy.
Used by Steward, API, and strategic_engine; dataclass for asdict() compatibility.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict


class GoalState(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    VISION_PENDING_CONFIRMATION = "vision_pending_confirmation"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class GoalLayer(Enum):
    VISION = "vision"
    OBJECTIVE = "objective"
    GOAL = "goal"


class GoalSource(Enum):
    USER_INPUT = "user_input"
    SYSTEM = "system"
    TOP_DOWN = "top_down"


@dataclass
class ObjectiveNode:
    """
    Single node in the Vision -> Objective -> Goal tree.
    Mutable; API and Steward update state/updated_at in place.
    """
    id: str
    title: str
    description: str
    layer: GoalLayer
    state: GoalState = GoalState.DRAFT
    source: GoalSource = GoalSource.USER_INPUT
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    goal_type: Optional[str] = None  # L1_SUBSTRATE | L2_FLOURISHING
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deadline: Optional[str] = None
    sub_tasks: List[Dict[str, Any]] = field(default_factory=list)
    success_count: int = 0
    skip_count: int = 0
    blocked_reason: Optional[str] = None
    worthiness_score: float = 0.0
    urgency_score: float = 0.0
    feasibility_score: float = 1.0
    estimated_hours: Optional[float] = None

    def __post_init__(self):
        from datetime import datetime
        now = datetime.now().isoformat()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
