"""
Sandbox Mode for AI Life OS.

Provides a simulation environment for testing strategies
without actually executing them.
"""
import copy
from datetime import datetime
from typing import Any, Dict, List, Optional


class Sandbox:
    """
    Sandbox environment for simulating AI Life OS operations.
    
    All operations in sandbox mode are isolated and do not
    affect the real state or event log.
    """
    
    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """
        Initialize sandbox with optional initial state.
        
        Args:
            initial_state: Starting state for simulation.
                          If None, uses empty initial state.
        """
        from core.event_sourcing import get_initial_state
        
        if initial_state:
            self._state = copy.deepcopy(initial_state)
        else:
            self._state = get_initial_state()
        
        self._event_log: List[Dict[str, Any]] = []
        self._action_results: List[Dict[str, Any]] = []
        self._is_active = True
    
    @property
    def state(self) -> Dict[str, Any]:
        """Get current sandbox state (read-only copy)."""
        return copy.deepcopy(self._state)
    
    @property
    def event_log(self) -> List[Dict[str, Any]]:
        """Get sandbox event log."""
        return self._event_log.copy()
    
    def apply_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply an event to the sandbox state.
        
        Args:
            event: Event dictionary to apply.
        
        Returns:
            New state after applying the event.
        """
        from core.event_sourcing import apply_event
        
        # 添加沙箱标记
        event = copy.deepcopy(event)
        event["_sandbox"] = True
        event["timestamp"] = datetime.now().isoformat()
        
        # 应用事件
        self._state = apply_event(self._state, event)
        self._event_log.append(event)
        
        return self.state
    
    def simulate_action(
        self,
        action: Dict[str, Any],
        outcome: str = "success"
    ) -> Dict[str, Any]:
        """
        Simulate executing an action.
        
        Args:
            action: Action to simulate.
            outcome: Expected outcome ("success" or "failure").
        
        Returns:
            Simulation result with state changes.
        """
        result = {
            "action": action,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat(),
            "state_before": copy.deepcopy(self._state)
        }
        
        # 根据结果类型生成事件
        if outcome == "success":
            event = {
                "type": "task_completed",
                "task_id": action.get("id"),
                "value": True
            }
        else:
            event = {
                "type": "task_failed",
                "task_id": action.get("id"),
                "failure_type": "simulated"
            }
        
        self.apply_event(event)
        result["state_after"] = copy.deepcopy(self._state)
        result["event"] = event
        
        self._action_results.append(result)
        
        return result
    
    def run_plan(
        self,
        plan: Dict[str, Any],
        outcome_map: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Simulate running an entire plan.
        
        Args:
            plan: Plan with actions to simulate.
            outcome_map: Dict mapping action IDs to outcomes.
                        If None, all actions succeed.
        
        Returns:
            List of simulation results for each action.
        """
        outcome_map = outcome_map or {}
        results = []
        
        for action in plan.get("actions", []):
            action_id = action.get("id", "")
            outcome = outcome_map.get(action_id, "success")
            result = self.simulate_action(action, outcome)
            results.append(result)
        
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the sandbox simulation.
        
        Returns:
            Summary with statistics and state changes.
        """
        successful = sum(
            1 for r in self._action_results
            if r["outcome"] == "success"
        )
        failed = len(self._action_results) - successful
        
        return {
            "total_actions": len(self._action_results),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self._action_results) if self._action_results else 0,
            "events_generated": len(self._event_log),
            "final_state": self.state
        }
    
    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        """
        Reset the sandbox to initial state.
        
        Args:
            new_state: Optional new initial state.
        """
        from core.event_sourcing import get_initial_state
        
        if new_state:
            self._state = copy.deepcopy(new_state)
        else:
            self._state = get_initial_state()
        
        self._event_log.clear()
        self._action_results.clear()


def create_sandbox_from_current() -> Sandbox:
    """
    Create a sandbox initialized with the current production state.
    
    Returns:
        Sandbox instance with current state.
    """
    from core.event_sourcing import rebuild_state
    
    current_state = rebuild_state()
    return Sandbox(initial_state=current_state)


def test_strategy(
    plan: Dict[str, Any],
    state: Optional[Dict[str, Any]] = None,
    outcome_scenarios: Optional[List[Dict[str, str]]] = None
) -> List[Dict[str, Any]]:
    """
    Test a planning strategy with multiple outcome scenarios.
    
    Args:
        plan: Plan to test.
        state: Initial state (uses current if None).
        outcome_scenarios: List of outcome maps to test.
    
    Returns:
        Results for each scenario.
    """
    if outcome_scenarios is None:
        # 默认测试：全部成功、全部失败、混合
        actions = plan.get("actions", [])
        action_ids = [a.get("id") for a in actions]
        
        outcome_scenarios = [
            {aid: "success" for aid in action_ids},  # 全部成功
            {aid: "failure" for aid in action_ids},  # 全部失败
        ]
        
        # 添加混合场景（一半成功）
        if len(action_ids) > 1:
            half = len(action_ids) // 2
            mixed = {}
            for i, aid in enumerate(action_ids):
                mixed[aid] = "success" if i < half else "failure"
            outcome_scenarios.append(mixed)
    
    results = []
    
    for scenario in outcome_scenarios:
        sandbox = Sandbox(initial_state=state)
        sandbox.run_plan(plan, scenario)
        
        results.append({
            "scenario": scenario,
            "summary": sandbox.get_summary()
        })
    
    return results
