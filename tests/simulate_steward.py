
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.steward import Steward
from core.config_manager import config

class TestStewardArchitecture(unittest.TestCase):
    
    def setUp(self):
        self.mock_state = {
            "time_state": {"current_date": "2026-01-27"},
            "identity": {"occupation": "Writer", "city": "Beijing"},
            "goals": {
                "active_goals": [
                    {
                        "id": "goal_1",
                        "title": "Write Novel",
                        "description": "Write a 50k word novel",
                        "created_at": "2026-01-01",
                        "type": "L2_FLOURISHING",
                        "sub_tasks": [{"id": "t1", "description": "Write Chapter 1", "status": "pending", "type": "session", "estimated_time": "60min", "difficulty": "high"}]
                    },
                    {
                        "id": "goal_2",
                        "title": "Buy Groceries",
                        "description": "Weekly grocery run",
                        "created_at": "2026-01-02",
                        "type": "L1_SUBSTRATE",
                        "sub_tasks": [{"id": "t2", "description": "Buy Milk", "status": "pending", "type": "task", "estimated_time": "15min", "difficulty": "low"}]
                    }
                ]
            }
        }
        self.steward = Steward(self.mock_state)

    def test_steward_renaming(self):
        """Verify class is named Steward."""
        self.assertEqual(self.steward.__class__.__name__, "Steward")

    @patch('core.steward.datetime')
    def test_energy_phase_deep_work(self, mock_datetime):
        """Test Deep Work phase blocks L1 tasks."""
        # Mock time to 10:00 (Deep Work: 09-13)
        mock_datetime.now.return_value = datetime(2026, 1, 27, 10, 0, 0)
        
        # Inject phases if not loaded
        if not config.ENERGY_PHASES:
             config.ENERGY_PHASES = {
                "09:00-13:00": "deep_work"
             }

        plan = self.steward.generate_plan()
        
        # Should contain L2 task
        l2_tasks = [a for a in plan['actions'] if a['priority'] == 'flourishing_session']
        self.assertTrue(len(l2_tasks) > 0, "Deep Work should allow L2 tasks")
        
        # Should NOT contain L1 task (unless maintenance, but our mock L1 is substrate_task)
        l1_tasks = [a for a in plan['actions'] if a['priority'] == 'substrate_task']
        self.assertEqual(len(l1_tasks), 0, f"Deep Work should block L1 tasks, found: {l1_tasks}")
        
        self.assertEqual(plan['energy_phase'], "deep_work")

    @patch('core.steward.datetime')
    def test_energy_phase_logistics(self, mock_datetime):
        """Test Logistics phase allows L1 tasks."""
        # Mock time to 15:00 (Logistics: 14-18)
        mock_datetime.now.return_value = datetime(2026, 1, 27, 15, 0, 0)
        
        plan = self.steward.generate_plan()
        
        # Should contain L1 task
        l1_tasks = [a for a in plan['actions'] if a['priority'] == 'substrate_task']
        self.assertTrue(len(l1_tasks) > 0, "Logistics should allow L1 tasks")
        
        self.assertEqual(plan['energy_phase'], "logistics")

if __name__ == '__main__':
    unittest.main()
