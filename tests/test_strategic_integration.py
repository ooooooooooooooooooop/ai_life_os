import pytest
from unittest.mock import patch, MagicMock
from core.steward import Steward
from core.strategic_engine.vision_inference import InferredVision

@patch("core.steward.GoalRegistry")
@patch("core.strategic_engine.vision_inference.infer_vision")
def test_steward_integration_vision(mock_infer, mock_registry_cls):
    # Setup Registry (Empty)
    mock_registry = MagicMock()
    mock_registry.goals = []
    mock_registry.visions = []
    mock_registry.objectives = []
    mock_registry_cls.return_value = mock_registry
    
    # Setup Vision Inference
    vision = InferredVision(
        title="Integration Vision",
        description="Desc",
        target_outcome="Outcome",
        confidence=0.9,
        reasoning_chain=[],
        information_edge=["Edge"],
        source_signals={},
        bhb_alignment="Aligned"
    )
    mock_infer.return_value = vision
    
    # Setup State (Not cold start)
    state = {
        "identity": {"name": "Test User", "city": "Shenzhen"},
        "time_state": {"current_date": "2026-01-27"}
    }
    
    steward = Steward(state)
    plan = steward.generate_plan()
    
    actions = plan["actions"]
    assert len(actions) > 0
    # Current behavior: inferred vision creates a maintenance notification action.
    vision_action = next((a for a in actions if "Integration Vision" in a.get("description", "")), None)

    assert vision_action is not None
    assert "Integration Vision" in vision_action["description"]
