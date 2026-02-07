"""
PriorityEngine: compute priority score for a goal in a given context.
Weights: worthiness, urgency, context_fit (phase vs goal_type).
"""
from typing import Any, Dict

from core.objective_engine.models import ObjectiveNode


class PriorityEngine:
    def __init__(self, config: Any):
        self._config = config

    def calculate_priority(self, goal: ObjectiveNode, context: Dict[str, Any]) -> float:
        w = getattr(goal, "worthiness_score", 0.0) or 0.0
        u = getattr(goal, "urgency_score", 0.0) or 0.0
        phase = (context or {}).get("energy_phase", "")
        goal_type = (getattr(goal, "goal_type", None) or "").upper()
        if "SUBSTRATE" in goal_type or not goal_type:
            context_fit = 0.2 if phase == "deep_work" else 0.5
        else:
            context_fit = 0.8 if phase == "deep_work" else 0.5
        return w * 0.3 + u * 0.3 + context_fit * 0.2 + 0.5 * 0.2
