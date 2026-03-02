import pytest
from unittest.mock import patch, MagicMock
from core.strategic_engine.vision_inference import infer_vision, InferredVision
import json

@patch("core.strategic_engine.vision_inference.get_llm")
@patch("core.strategic_engine.vision_inference.parse_bhb")
@patch("core.strategic_engine.vision_inference.search_market_trends")
def test_infer_vision(mock_search, mock_bhb, mock_get_llm):
    # Setup Mocks
    mock_bhb.return_value = MagicMock(
        philosophy="Test Philosophy",
        strategic_goals=[],
        life_metrics=[]
    )
    mock_search.return_value = []
    
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    
    # Mock LLM Success Response
    mock_response = MagicMock()
    mock_response.success = True
    mock_response.content = json.dumps({
        "title": "Test Vision",
        "description": "Test Desc",
        "target_outcome": "Outcome",
        "confidence": 0.8,
        "reasoning_chain": ["reason1"],
        "information_edge": ["edge1"],
        "bhb_alignment": "aligned"
    })
    mock_llm.generate.return_value = mock_response
    
    # Run
    state = {"identity": {"city": "Shenzhen"}, "capability": {"skills": ["Python"]}}
    result = infer_vision(state)
    
    # Assert
    assert isinstance(result, InferredVision)
    assert result.title == "Test Vision"
    assert result.confidence == 0.8
    assert result.source_signals["identity"]["city"] == "Shenzhen"
    
@patch("core.strategic_engine.vision_inference.get_llm")
def test_infer_vision_failure(mock_get_llm):
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    
    mock_response = MagicMock()
    mock_response.success = False
    mock_llm.generate.return_value = mock_response
    
    state = {}
    result = infer_vision(state, enable_search=False)
    assert result is None
