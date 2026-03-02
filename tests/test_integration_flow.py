import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.steward import Steward
from core.objective_engine.registry import GoalRegistry
from core.objective_engine.models import ObjectiveNode, GoalLayer, GoalState
from core.config_manager import config

class TestIntegrationFlow:
    """
    Test the integration between GoalRegistry and Steward.
    Design Doc Section 7.2 Integration Test.
    """
    
    def test_steward_fetches_registry_goals(self, tmp_path):
        # 1. Setup Mock Registry
        import core.objective_engine.registry as registry_module
        original_path = registry_module.REGISTRY_PATH
        registry_module.REGISTRY_PATH = tmp_path / "integration_goals.json"
        
        try:
            # Create a goal in registry
            registry = GoalRegistry()
            goal = ObjectiveNode(
                id="int_001",
                title="Integration Goal",
                description="Testing full flow",
                layer=GoalLayer.GOAL,
                state=GoalState.ACTIVE,
                goal_type="L1_SUBSTRATE",
                sub_tasks=[{"id": "st1", "description": "Subtask 1", "status": "pending", "estimated_time": "30min", "difficulty": "low"}]
            )
            registry.add_node(goal)
            
            # 2. Setup Steward State
            state = {
                "time_state": {"current_date": "2026-01-27"},
                "identity": {"city": "TestCity", "occupation": "Tester"},
                "goals": {"active_goals": []} # Steward should ignore this now
            }
            
            # 3. Generate Plan
            steward = Steward(state)
            # Inject our registry instance (though it should load from same path)
            steward.registry = registry
            
            # Mock _get_current_phase to allow L1 tasks (logistics phase)
            # This bypasses the time check which fails during deep_work hours
            steward._get_current_phase = lambda: "logistics"

            plan = steward.generate_plan()
            
            # 4. Verify
            actions = plan.get("actions", [])
            # Should have at least the goal action
            goal_actions = [a for a in actions if a.get("metadata", {}).get("goal_id") == "int_001"]
            
            if not goal_actions:
                print(f"DEBUG: Plan Actions: {actions}")
            
            assert len(goal_actions) > 0
            assert "Integration Goal" in goal_actions[0]["description"]
            
        finally:
            registry_module.REGISTRY_PATH = original_path
