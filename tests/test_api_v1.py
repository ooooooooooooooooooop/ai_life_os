from fastapi.testclient import TestClient
from web.backend.app import app
from datetime import datetime
import json
import pytest

client = TestClient(app)

def test_read_state():
    response = client.get("/api/v1/state")
    assert response.status_code == 200
    data = response.json()
    assert "identity" in data
    assert "energy_phase" in data
    assert "active_tasks" in data

def test_goal_feedback_404():
    # Test a real endpoint with non-existent ID
    data = {"message": "done"}
    response = client.post("/api/v1/goals/non_existent_id/feedback", json=data)
    assert response.status_code == 404
