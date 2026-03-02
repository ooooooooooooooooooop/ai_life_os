import os
import pytest
from unittest.mock import patch, MagicMock
from core.strategic_engine.info_sensing import search_market_trends, _execute_search, MarketInsight

@patch.dict(os.environ)
def test_search_no_api_key_fallback():
    """Test fallback to mock when API key is missing."""
    if "SERPER_API_KEY" in os.environ:
        del os.environ["SERPER_API_KEY"]
    """Test fallback to mock when API key is missing."""
    results = search_market_trends("python", limit=1)
    # Should get mock result
    assert len(results) > 0
    assert "Mock" in results[0].insight or "mock" in results[0].source

@patch.dict(os.environ, {"SERPER_API_KEY": "fake_key"})
@patch("requests.request")
def test_search_with_api_key(mock_request):
    """Test API call when key is present."""
    # Mock Response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "organic": [
            {
                "title": "Python Job Market",
                "link": "https://example.com/jobs",
                "snippet": "Python is booming."
            }
        ]
    }
    mock_request.return_value = mock_resp
    
    results = search_market_trends("python", limit=1)
    
    assert len(results) == 1
    assert results[0].insight == "Python is booming."
    assert results[0].source == "https://example.com/jobs"
    
    # Verify API called with correct headers
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs['headers']['X-API-KEY'] == "fake_key"

@patch.dict(os.environ, {"SERPER_API_KEY": "fake_key"})
@patch("requests.request")
def test_search_api_failure(mock_request):
    """Test graceful handling of API failure."""
    mock_request.side_effect = Exception("Network Error")
    
    results = search_market_trends("python", limit=1)
    # Should return empty or handle gracefully (in this implementation, it skips failed ones)
    assert len(results) == 0
