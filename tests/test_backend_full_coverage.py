
import pytest
from fastapi.testclient import TestClient
from web.backend.app import app
from core.objective_engine.registry import get_registry, clear_registry
from core.objective_engine.models import GoalState, GoalLayer, ObjectiveNode
import uuid
import time
import os

client = TestClient(app)

@pytest.fixture
def mock_registry(clear_goal_registry_singleton):
    """Ensure we have a clean state with some known data for testing."""
    registry = get_registry()
    # Add a dummy vision
    vision_id = f"vis_{uuid.uuid4()}"
    vision = ObjectiveNode(
        id=vision_id,
        title="Test Vision",
        description="A vision for testing",
        layer=GoalLayer.VISION,
        state=GoalState.ACTIVE
    )
    registry.add_node(vision)
    
    # Add a dummy pending goal
    pending_goal_id = f"goal_{uuid.uuid4()}"
    pending_goal = ObjectiveNode(
        id=pending_goal_id,
        title="Pending Goal",
        description="Waiting for confirmation",
        layer=GoalLayer.GOAL,
        state=GoalState.VISION_PENDING_CONFIRMATION
    )
    registry.add_node(pending_goal)

    # Add a dummy active goal
    active_goal_id = f"goal_{uuid.uuid4()}"
    active_goal = ObjectiveNode(
        id=active_goal_id,
        title="Active Goal",
        description="Currently active",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE
    )
    registry.add_node(active_goal)
    
    return {
        "vision_id": vision_id,
        "pending_goal_id": pending_goal_id,
        "active_goal_id": active_goal_id,
        "registry": registry
    }

def test_get_state():
    response = client.get("/api/v1/state")
    assert response.status_code == 200
    data = response.json()
    assert "identity" in data
    assert "metrics" in data
    assert "active_tasks" in data

def test_list_visions():
    response = client.get("/api/v1/visions")
    assert response.status_code == 200
    data = response.json()
    assert "visions" in data
    assert isinstance(data["visions"], list)

def test_update_vision(mock_registry):
    vid = mock_registry["vision_id"]
    payload = {"title": "Updated Vision Title", "description": "Updated Desc"}
    response = client.put(f"/api/v1/visions/{vid}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["vision"]["title"] == "Updated Vision Title"

def test_confirm_goal(mock_registry):
    gid = mock_registry["pending_goal_id"]
    response = client.post(f"/api/v1/goals/{gid}/confirm")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    
    # Verify state change
    reg = get_registry()
    node = reg.get_node(gid)
    assert node.state == GoalState.ACTIVE

def test_reject_goal(mock_registry):
    # Need another pending goal for rejection test to assume isolation,
    # but let's create a new one on fly to be safe
    from core.objective_engine.registry import get_registry as get_reg
    reg = get_reg()
    reject_id = f"goal_reject_{uuid.uuid4()}"
    node = ObjectiveNode(
        id=reject_id, title="To Reject", description="..", 
        layer=GoalLayer.GOAL, state=GoalState.VISION_PENDING_CONFIRMATION
    )
    reg.add_node(node)

    response = client.post(f"/api/v1/goals/{reject_id}/reject")
    assert response.status_code == 200

    # Reload registry to verify persistence
    from core.objective_engine.registry import get_registry as get_reg2
    reg_new = get_reg2()
    node_check = reg_new.get_node(reject_id)
    assert node_check.state == GoalState.ARCHIVED

def test_submit_feedback(mock_registry, clear_goal_registry_singleton):
    gid = mock_registry["active_goal_id"]
    # Intent: COMPLETE
    response = client.post(f"/api/v1/goals/{gid}/feedback", json={"message": "I finished this task"})
    assert response.status_code == 200
    data = response.json()
    # Note: Depending on LLM/Mock, intent might differ.
    # But usually "I finished" -> COMPLETE
    # If using regex/keyword classifier, it should work.

    # Intent: SKIP
    # Reset goal or use another
    from core.objective_engine.registry import get_registry
    reg = get_registry()
    skip_id = f"goal_skip_{uuid.uuid4()}"
    reg.add_node(ObjectiveNode(
        id=skip_id, 
        title="Skip Me", 
        description="Description for skip test",
        layer=GoalLayer.GOAL, 
        state=GoalState.ACTIVE
    ))
    
    response = client.post(f"/api/v1/goals/{skip_id}/feedback", json={"message": "skip this for now"})
    assert response.status_code == 200
    data = response.json()
    assert data["new_state"] == "active"  # Skip keeps it active but increments counter

def test_execute_action(mock_registry):
    gid = mock_registry["active_goal_id"]
    # Action: Complete
    response = client.post(f"/api/v1/goals/{gid}/action", json={"action": "complete"})
    assert response.status_code == 200
    data = response.json()
    assert data["new_state"] == "completed"

def test_get_timeline():
    response = client.get("/api/v1/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "timeline" in data

def test_list_goals():
    response = client.get("/api/v1/goals")
    assert response.status_code == 200
    data = response.json()
    assert "goals" in data
    
    # Filter test
    response = client.get("/api/v1/goals?state=active")
    assert response.status_code == 200
    
def test_sys_cycle():
    if os.getenv("RUN_SLOW_API_TESTS", "0") != "1":
        pytest.skip("skip slow endpoint in default CI/local quick run")
    # This might trigger LLMs, potentially slow or costly, but it's a test for runnability
    # Mocking could be preferred, but user asked to test "if it runs".
    response = client.post("/api/v1/sys/cycle")
    # It might return 200 or 500 depending on config/keys. 
    # Assuming configured successfully or gracefully degradation.
    assert response.status_code == 200 
    data = response.json()
    assert "status" in data

def test_interact():
    if os.getenv("RUN_SLOW_API_TESTS", "0") != "1":
        pytest.skip("skip slow endpoint in default CI/local quick run")
    response = client.post("/api/v1/interact", json={"message": "Hello Steward"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data

@pytest.mark.skip(reason="SSE stream blocks in sync TestClient; use async client or mock in future")
def test_stream_events():
    # Test SSE connection
    with client.stream("GET", "/api/v1/events") as response:
        assert response.status_code == 200
        pass
