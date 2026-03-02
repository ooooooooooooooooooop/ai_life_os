import pytest
from unittest.mock import patch, MagicMock
from core.strategic_engine.milestone_decomposer import decompose_vision
from core.objective_engine.models import GoalLayer
import json

@patch("core.strategic_engine.milestone_decomposer.get_llm")
def test_decompose_vision(mock_get_llm):
    # Mock LLM
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    
    # Mock LLM Success Response
    mock_response = MagicMock()
    mock_response.success = True
    mock_response.content = json.dumps({
        "objectives": [
            {
                "title": "Obj 1",
                "description": "Desc 1",
                "deadline": "2026-03-31",
                "goals": [{"title": "Goal 1", "description": "G Desc 1", "deadline": "2026-02-28"}]
            }
        ]
    })
    mock_llm.generate.return_value = mock_response
    
    nodes = decompose_vision("Vision", "Desc")
    
    assert len(nodes) == 2  # 1 Objective + 1 Goal
    assert nodes[0].layer == GoalLayer.OBJECTIVE
    assert nodes[1].layer == GoalLayer.GOAL
    assert nodes[1].parent_id == nodes[0].id
