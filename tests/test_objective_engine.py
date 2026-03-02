import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime
from core.objective_engine.models import ObjectiveNode, GoalLayer, GoalState
from core.objective_engine.registry import GoalRegistry
from core.objective_engine.priority import PriorityEngine
from core.objective_engine.triggers import TriggerEngine, TriggerContext, TriggerType
from core.objective_engine.throttle import ThrottleGate
from core.objective_engine.quality import QualityGate
from core.config_manager import config

class TestObjectiveEngine:
    
    def test_models_creation(self):
        node = ObjectiveNode(
            id="test_001",
            title="Test Goal",
            description="Just a test",
            layer=GoalLayer.GOAL,
            state=GoalState.DRAFT
        )
        assert node.id == "test_001"
        assert node.state == GoalState.DRAFT
        
    def test_registry_crud(self, tmp_path):
        # Mock REGISTRY_PATH
        import core.objective_engine.registry as registry_module
        original_path = registry_module.REGISTRY_PATH
        registry_module.REGISTRY_PATH = tmp_path / "goals.json"
        
        try:
            registry = GoalRegistry()
            node = ObjectiveNode(
                id="g1", title="G1", description="D1", layer=GoalLayer.GOAL
            )
            registry.add_node(node)
            
            # Verify in memory
            assert registry.get_node("g1").title == "G1"
            
            # Verify persistence
            registry2 = GoalRegistry()
            assert registry2.get_node("g1").title == "G1"
            
        finally:
            registry_module.REGISTRY_PATH = original_path

    def test_priority_engine(self):
        engine = PriorityEngine(config)
        goal = ObjectiveNode(
            id="g1", title="G1", description="D1", layer=GoalLayer.GOAL,
            worthiness_score=0.8,
            urgency_score=0.5
        )
        context = {"energy_phase": "deep_work"}
        
        # Test 1: Substrate in Deep Work -> Context Fit Low (0.2)
        # Score = 0.8*0.3 + 0.5*0.3 + 0.2*0.2 + 0.5*0.2 = 0.24 + 0.15 + 0.04 + 0.10 = 0.53
        score = engine.calculate_priority(goal, context)
        assert 0.5 <= score <= 0.6
        
    def test_trigger_engine(self):
        engine = TriggerEngine(config)
        ctx = TriggerContext(
            trigger_type=TriggerType.TIME_BASED,
            trigger_source="daily",
            timestamp="now",
            cooldown_key="daily_gen"
        )
        
        assert engine.should_trigger(ctx) is True
        
        # Set cooldown
        engine.set_cooldown("daily_gen")
        assert engine.should_trigger(ctx) is False
        
    def test_throttle_gate(self):
        gate = ThrottleGate(config)
        
        active_goals = [
            ObjectiveNode(id="l1_1", title="L1", description="desc", layer=GoalLayer.GOAL, state=GoalState.ACTIVE, goal_type="L1_SUBSTRATE"),
            ObjectiveNode(id="l1_2", title="L1", description="desc", layer=GoalLayer.GOAL, state=GoalState.ACTIVE, goal_type="L1_SUBSTRATE"),
            ObjectiveNode(id="l1_3", title="L1", description="desc", layer=GoalLayer.GOAL, state=GoalState.ACTIVE, goal_type="L1_SUBSTRATE"),
            ObjectiveNode(id="l1_4", title="L1", description="desc", layer=GoalLayer.GOAL, state=GoalState.ACTIVE, goal_type="L1_SUBSTRATE"),
            ObjectiveNode(id="l1_5", title="L1", description="desc", layer=GoalLayer.GOAL, state=GoalState.ACTIVE, goal_type="L1_SUBSTRATE")
        ]
        
        new_l1 = ObjectiveNode(id="new_l1", title="New", description="desc", layer=GoalLayer.GOAL, goal_type="L1_SUBSTRATE")
        assert gate.check_activation_cap(active_goals, new_l1) is False
        
        new_l2 = ObjectiveNode(id="new_l2", title="New L2", description="desc", layer=GoalLayer.GOAL, goal_type="L2_FLOURISHING")
        assert gate.check_activation_cap(active_goals, new_l2) is True # L2 cap is separate (0/2)

    def test_quality_gate(self):
        gate = QualityGate(config)
        goal = ObjectiveNode(id="g1", title="G1", description="desc", layer=GoalLayer.GOAL, estimated_hours=50)
        context = {"available_weekly_hours": 40}
        
        reason = gate.check_constraints(goal, context)
        assert reason is not None
        assert "Insufficient time" in reason
