import pytest
import unittest.mock
from textual.pilot import Pilot
from core.objective_engine.models import GoalState, GoalLayer, ObjectiveNode
from core.objective_engine.registry import GoalRegistry

ui_app = pytest.importorskip("ui.app")
vision_modal = pytest.importorskip("ui.modals.vision_confirm")
AILifeApp = ui_app.AILifeApp
VisionConfirmModal = vision_modal.VisionConfirmModal

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_vision_confirmation_flow():
    """Verify that a pending vision triggers the review flow and confirmation updates registry."""
    
    # 1. Setup App with Mock Registry
    app = AILifeApp()
    mock_registry = unittest.mock.MagicMock()
    app.registry = mock_registry
    app.steward.registry = mock_registry # Update steward too
    
    # Create a pending vision
    pending_vision = ObjectiveNode(
        id="vision_1",
        title="Pending Vision",
        description="A bold new future.",
        layer=GoalLayer.VISION,
        state=GoalState.VISION_PENDING_CONFIRMATION
    )
    
    # Mock registry behavior
    mock_registry.visions = [pending_vision]
    mock_registry.objectives = []
    mock_registry.goals = []
    
    async with app.run_test() as pilot:
        # 1. Dashboard Load
        dashboard = app.screen
        assert "DashboardScreen" in str(type(dashboard))
        
        # Verify Button is Visible (removed .hidden class)
        btn = dashboard.query_one("#btn-review-vision")
        assert not btn.has_class("hidden")
        
        # 2. Click Review Button
        await pilot.click("#btn-review-vision")
        await pilot.pause()
        
        # Verify Modal Pushed
        assert isinstance(app.screen, VisionConfirmModal)
        assert app.screen.vision["title"] == "Pending Vision"
        
        # 3. Click Confirm in Modal
        await pilot.click("#btn-confirm")
        await pilot.pause()
        
        # Verify Modal Dismissed and Dashboard Active
        assert "DashboardScreen" in str(type(app.screen))
        
        # 4. Verify Node Updated
        assert pending_vision.state == GoalState.ACTIVE
        assert pending_vision.updated_at != "now" # Should be ISO format
        
        # Verify Save Called
        mock_registry.save.assert_called_once()
        
        # Verify Button Hidden (if no more pending)
        # We need to ensure refresh_dashboard logic sees the updated state.
        # Since we modified the object inside the list, and refresh checked `v.state`...
        # It should see ACTIVE and not yield True for "has_pending".
        # So button should be hidden.
        
        # Note: Pilot needs to wait for refresh_dashboard to complete? 
        # on_vision_confirmed calls self.refresh_dashboard()
        
        btn = dashboard.query_one("#btn-review-vision")
        assert btn.has_class("hidden")
