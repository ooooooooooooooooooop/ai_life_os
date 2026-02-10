"""
ThrottleGate: cap on active L1 (substrate) and L2 (flourishing) goals.
"""
from typing import Any, List

from core.objective_engine.models import ObjectiveNode


class ThrottleGate:
    L1_CAP = 5
    L2_CAP = 2

    def __init__(self, config: Any):
        self._config = config

    def check_activation_cap(
        self,
        active_goals: List[ObjectiveNode],
        new_goal: ObjectiveNode,
    ) -> bool:
        gt = (getattr(new_goal, "goal_type", None) or "").upper()
        if "L1_SUBSTRATE" in gt:
            l1_count = sum(
                1
                for g in active_goals
                if (getattr(g, "goal_type", None) or "").upper() == "L1_SUBSTRATE"
            )
            return l1_count < self.L1_CAP
        if "L2_FLOURISHING" in gt:
            l2_count = sum(
                1
                for g in active_goals
                if (getattr(g, "goal_type", None) or "").upper() == "L2_FLOURISHING"
            )
            return l2_count < self.L2_CAP
        return True
