
from fastapi.testclient import TestClient
from web.backend.app import app
from core.objective_engine.registry import GoalRegistry
from core.objective_engine.models import GoalState, GoalLayer, ObjectiveNode
from datetime import datetime
import pytest
import shutil
from pathlib import Path

client = TestClient(app)

@pytest.fixture
def clean_registry():
    # Setup: backup registry
    registry_path = Path("data/goal_registry.json")
    backup_path = Path("data/goal_registry.json.bak")
    if registry_path.exists():
        shutil.copy(registry_path, backup_path)
    
    yield
    
    # Teardown: restore
    if backup_path.exists():
        shutil.move(backup_path, registry_path)

def test_goal_action_endpoints(clean_registry):
    # 1. Create a dummy goal directly in registry
    registry = GoalRegistry()
    goal = ObjectiveNode(
        id="test_action_goal",
        title="Test Action Goal",
        description="Testing API",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE
    )
    registry.add_node(goal)
    
    # 2. Test SKIP action
    response = client.post("/api/v1/goals/test_action_goal/action", json={"action": "skip", "reason": "bored"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    # State should remain ACTIVE
    assert data["new_state"] == "active"
    
    # Verify modification in registry
    # MUST re-load registry to see changes made by API (process isolation simulation)
    registry = GoalRegistry()
    updated_goal = registry.get_node("test_action_goal")
    assert updated_goal.skip_count == 1
    
    # 3. Test COMPLETE action
    response = client.post("/api/v1/goals/test_action_goal/action", json={"action": "complete"})
    assert response.status_code == 200
    data = response.json()
    assert data["new_state"] == "completed"
    
    registry = GoalRegistry()
    updated_goal = registry.get_node("test_action_goal")
    assert updated_goal.state == GoalState.COMPLETED
    assert updated_goal.success_count == 1


def test_timeline_endpoint(clean_registry):
    registry = GoalRegistry()
    # Ensure at least one active goal
    goal = ObjectiveNode(
        id="test_timeline_goal",
        title="Test Timeline",
        description="Testing Timeline",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE
    )
    registry.add_node(goal)
    
    response = client.get("/api/v1/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "timeline" in data
    assert len(data["timeline"]) >= 1
    # 不假定顺序：registry 可能含其他测试的 goal，只断言本用例加入的 goal 在 timeline 中
    assert any(item["id"] == "test_timeline_goal" for item in data["timeline"])
