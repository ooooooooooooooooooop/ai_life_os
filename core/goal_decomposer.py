"""
Goal Decomposer for AI Life OS.

Breaks down high-level user goals into executable sub-tasks or flow sessions.
Implements the Dual-Layer Architecture (Substrate vs Flourishing) from core_design.md.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from core.llm_adapter import get_llm
from core.utils import load_prompt, parse_llm_json
from core.config_manager import config


class GoalType(str, Enum):
    """
    Distinguishes between L1 (Maintenance) and L2 (Growth) goals.
    See docs/core_design.md for philosophy.
    """
    SUBSTRATE = "L1_SUBSTRATE"      # Maintenance, Chores, NPC Mode -> Efficiency
    FLOURISHING = "L2_FLOURISHING"  # Deep Work, Connection, Player Mode -> Quality


@dataclass
class SubTask:
    """A single unit of work."""
    id: str
    description: str
    estimated_time: str  # e.g., "30min", "2h"
    difficulty: str  # low, medium, high
    type: str = "task" # "task" (L1) or "session" (L2)
    prerequisite: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Goal:
    """A high-level goal with its sub-tasks/sessions."""
    id: str
    title: str
    description: str
    created_at: str
    type: GoalType = GoalType.SUBSTRATE
    deadline: Optional[str] = None
    sub_tasks: List[SubTask] = None
    status: str = "active"  # active, completed, abandoned
    
    def __post_init__(self):
        if self.sub_tasks is None:
            self.sub_tasks = []
            
        if isinstance(self.type, str):
            # Compatibility with string inputs
            type_str = self.type.upper()
            if "SUBSTRATE" in type_str:
                self.type = GoalType.SUBSTRATE
            elif "FLOURISHING" in type_str:
                self.type = GoalType.FLOURISHING
            else:
                self.type = GoalType.SUBSTRATE
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["type"] = self.type.value
        result["sub_tasks"] = [st.to_dict() for st in self.sub_tasks]
        return result
    
    @property
    def progress(self) -> float:
        """Calculate completion progress (0.0 - 1.0)."""
        if not self.sub_tasks:
            return 0.0
        completed = sum(1 for t in self.sub_tasks if t.status == "completed")
        return completed / len(self.sub_tasks)



def decompose_goal_with_llm(
    goal_title: str,
    goal_description: str,
    goal_type: GoalType = GoalType.SUBSTRATE,
    context: Optional[Dict[str, Any]] = None
) -> List[SubTask]:
    """
    Use LLM to decompose a goal based on its layer (L1 vs L2).
    """
    llm = get_llm("strategic_brain")
    
    # Select Prompt based on GoalType
    if goal_type == GoalType.SUBSTRATE:
        system_prompt = load_prompt("goal_substrate")
        prompt_suffix = "请将此目标分解为 NPC 可执行的原子指令。"
    else:
        system_prompt = load_prompt("goal_flourishing")
        prompt_suffix = "请规划 1-3 个深度体验时段 (Sessions)。"
    
    if not system_prompt:
        # Fallback if prompt file missing
        system_prompt = "You are a task decomposer."
    
    prompt = f"""目标 ({goal_type.value}): {goal_title}
详细描述: {goal_description}
"""
    if context:
        prompt += f"\n用户背景:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
    
    prompt += f"\n{prompt_suffix}"
    
    response = llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.3 if goal_type == GoalType.SUBSTRATE else 0.6, # L2 can be more creative
        max_tokens=800
    )
    
    sub_tasks = []
    
    if response.success and response.content:
        try:
            result = parse_llm_json(response.content)
            if result:
                raw_tasks = result.get("sub_tasks", [])
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                for i, t in enumerate(raw_tasks):
                    sub_tasks.append(SubTask(
                        id=f"subtask_{timestamp}_{i}",
                        description=t.get("description", ""),
                        estimated_time=t.get("estimated_time", "30min"),
                        difficulty=t.get("difficulty", "medium"),
                        type=t.get("type", "task"),
                        prerequisite=t.get("prerequisite")
                    ))
        except (json.JSONDecodeError, KeyError):
            # Fallback
            sub_tasks.append(SubTask(
                id=f"subtask_{datetime.now().strftime('%Y%m%d%H%M%S')}_0",
                description=f"手动规划: {goal_title}",
                estimated_time="30min",
                difficulty="medium"
            ))
            
    return sub_tasks


def create_goal(
    title: str,
    description: str,
    goal_type: GoalType = GoalType.SUBSTRATE,
    deadline: Optional[str] = None,
    auto_decompose: bool = True,
    context: Optional[Dict[str, Any]] = None
) -> Goal:
    """
    Create a new goal with layer awareness.
    """
    goal = Goal(
        id=f"goal_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        title=title,
        description=description,
        type=goal_type,
        created_at=datetime.now().isoformat(),
        deadline=deadline
    )
    
    if auto_decompose:
        goal.sub_tasks = decompose_goal_with_llm(title, description, goal_type, context)
    
    return goal


def get_next_actionable_task(goal: Goal) -> Optional[SubTask]:
    """
    Get the next actionable item. 
    """
    completed_ids = {t.id for t in goal.sub_tasks if t.status == "completed"}
    
    for task in goal.sub_tasks:
        if task.status != "pending":
            continue
        if task.prerequisite is None or task.prerequisite in completed_ids:
            return task
    return None


def update_task_status(goal: Goal, task_id: str, new_status: str) -> bool:
    for task in goal.sub_tasks:
        if task.id == task_id:
            task.status = new_status
            return True
    return False
