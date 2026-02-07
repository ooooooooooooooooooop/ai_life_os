"""
QualityGate: constraint checks (e.g. time budget) before activating a goal.
"""
from typing import Any, Optional

from core.objective_engine.models import ObjectiveNode


class QualityGate:
    def __init__(self, config: Any):
        self._config = config

    def check_constraints(self, goal: ObjectiveNode, context: dict) -> Optional[str]:
        hours = getattr(goal, "estimated_hours", None)
        if hours is None:
            return None
        available = (context or {}).get("available_weekly_hours")
        if available is not None and hours > available:
            return "Insufficient time: goal estimated hours exceed available weekly hours."
        return None
