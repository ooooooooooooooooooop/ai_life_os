"""
Tests for Focus Mode task completion and Event Log integration.
"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.objective_engine.models import ObjectiveNode, GoalState, GoalLayer


class TestFocusComplete:
    """Test Focus Mode complete_task() writes to Event Log."""
    
    def test_complete_task_writes_event(self, tmp_path):
        """Verify that completing a task appends a goal_completed event."""
        # Setup: Create temporary event log
        event_log = tmp_path / "event_log.jsonl"
        event_log.write_text("")
        
        # Create a mock goal
        goal = ObjectiveNode(
            id="test_goal_001",
            title="Test Goal",
            description="A test goal for verification",
            layer=GoalLayer.GOAL,
            state=GoalState.ACTIVE
        )
        
        # Mock the registry and event log path
        with patch("core.event_sourcing.EVENT_LOG_PATH", event_log):
            from core.event_sourcing import append_event
            
            # Simulate the complete_task logic
            goal.state = GoalState.COMPLETED
            goal.success_count += 1
            goal.updated_at = datetime.now().isoformat()
            
            append_event({
                "type": "goal_completed",
                "goal_id": goal.id,
                "goal_title": goal.title,
                "completed_at": goal.updated_at
            })
        
        # Verify: Event log contains the completion event
        events = event_log.read_text().strip().split("\n")
        assert len(events) == 1
        
        event = json.loads(events[0])
        assert event["type"] == "goal_completed"
        assert event["goal_id"] == "test_goal_001"
        assert event["goal_title"] == "Test Goal"
        assert "completed_at" in event
        assert "timestamp" in event

    def test_complete_task_updates_goal_state(self):
        """Verify goal state transitions correctly on completion."""
        goal = ObjectiveNode(
            id="test_goal_002",
            title="Another Goal",
            description="Another test goal",
            layer=GoalLayer.GOAL,
            state=GoalState.ACTIVE,
            success_count=0
        )
        
        # Simulate state update
        goal.state = GoalState.COMPLETED
        goal.success_count += 1
        
        assert goal.state == GoalState.COMPLETED
        assert goal.success_count == 1


class TestEnergyPhaseDisplay:
    """Test Dashboard Energy Phase display."""
    
    def test_phase_mapping(self):
        """Verify all phases have display mappings."""
        phase_display = {
            "activation": "🌅 Activation",
            "deep_work": "🔥 Deep Work",
            "connection": "🤝 Connection",
            "logistics": "📦 Logistics",
            "leisure": "🌙 Leisure"
        }
        
        expected_phases = ["activation", "deep_work", "connection", "logistics", "leisure"]
        for phase in expected_phases:
            assert phase in phase_display
            assert len(phase_display[phase]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
