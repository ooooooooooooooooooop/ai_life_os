"""
Tests for Steward Core (formerly Planner).
"""
import unittest
import sys
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.steward import Steward
from core.event_sourcing import get_initial_state
from core.llm_adapter import BaseLLMAdapter, LLMResponse, get_llm

# Mock LLM
class MockLLM(BaseLLMAdapter):
    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=1000) -> LLMResponse:
        return LLMResponse(content="", model="mock", error="Mocked")

class TestSteward(unittest.TestCase):
    
    def setUp(self):
        self.state = get_initial_state()
        # Mocking time for consistency
        self.state["time_state"]["current_date"] = "2026-01-01"
        self.state["identity"]["age"] = 25
    
    def test_maintenance_actions(self):
        # Case: Missing current_date triggers sync (but we set it above, so let's unset it)
        self.state["time_state"]["current_date"] = ""
        
        steward = Steward(self.state)
        actions = steward._generate_maintenance_actions()
        
        self.assertTrue(any(a["id"] == "maint_time_sync" for a in actions))
    
    def test_plan_generation_structure(self):
        steward = Steward(self.state)
        plan = steward.generate_plan()
        
        self.assertIn("actions", plan)
        self.assertIn("audit", plan)
        self.assertIn("generated_at", plan)
        
        # Verify audit trailing
        audit = plan["audit"]
        self.assertIn("decision_reason", audit)
        self.assertIn("used_state_fields", audit)

if __name__ == "__main__":
    unittest.main()
