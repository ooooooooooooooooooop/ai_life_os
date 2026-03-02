import pytest
from unittest.mock import patch
from core.strategic_engine.info_sensing import search_market_trends, MarketInsight

@patch("core.strategic_engine.info_sensing._execute_search")
def test_search_market_trends(mock_execute):
    # Setup mock
    mock_execute.return_value = MarketInsight(
        query="test",
        insight="test insight",
        source="test source",
        relevance=1.0
    )
    
    results = search_market_trends("Python", limit=2)
    
    assert len(results) == 2
    assert results[0].insight == "test insight"
    assert mock_execute.call_count == 2
