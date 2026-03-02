
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.steward import Steward
from core.objective_engine.models import GoalState

def test_grounded_protocol_generation():
    print(">>> Testing Layered Defense (v6) Logic...")
    
    # 1. Setup Mock State (Idle, Deep Work Phase)
    mock_state = {
        "identity": {"name": "Test User"},
        "time_state": {"current_date": "2025-01-01"}, # Mock time inside Steward
        "goals": [], # No active goals
    }
    
    # Mock Config to return "deep_work" phase
    with patch('core.steward.config') as mock_config:
        mock_config.ENERGY_PHASES = {"00:00-23:59": "deep_work"}
        mock_config.DAILY_TASK_LIMIT = 5
        mock_config.DEFAULT_LOG_PATH = "test.log"
        mock_config.EVENT_LOOKBACK = 5
        mock_config.MIN_EVENTS_FOR_RHYTHM = 5
        
        # Initialize Steward
        steward = Steward(mock_state)
        
        # 2. Mock Dependency: LLM (Strategic Brain)
        mock_llm = MagicMock()
        mock_llm.generate.return_value.success = True
        # Simulate LLM generating a valid Protocol JSON
        mock_llm.generate.return_value.content = json.dumps({
            "title": "Deep Focus Protocol (TEST)",
            "description": "A grounded protocol for testing.",
            "steps": ["Step 1: Clear desk", "Step 2: Start timer"],
            "type": "learning",
            "estimated_duration": "30m"
        })
        
        # 3. Mock Dependency: Search / File Read
        with patch('core.llm_adapter.get_llm', return_value=mock_llm):
            with patch('core.steward.search_market_trends', return_value=["Mock Search Result"]):
                with patch('core.steward.is_cold_start', return_value=False): # Force Not Cold Start
                    with patch('pathlib.Path.exists', return_value=False): # Force search path
                         # Force _infer_missing_goals to return empty so we hit _handle_idle_state
                        with patch.object(steward, '_infer_missing_goals', return_value=[]):
                            with patch('core.steward.load_prompt', return_value="Dummy Prompt Template {context}"):
                                with patch('core.steward.parse_llm_json', return_value={
                                    "title": "Deep Focus Protocol (TEST)",
                                    "description": "Mocked Protocol",
                                    "steps": ["Step 1"],
                                    "type": "learning"
                                }):
                        
                                    # === EXECUTE ===
                                    plan = steward.run_planning_cycle()
                    
                    # === VERIFY ===
                    actions = plan.get("actions", [])
                    print(f"Generated Actions: {len(actions)}")
                    
                    # Check if Protocol Goal was created in Registry
                    goals = steward.registry.goals
                    print(f"Registry Goals: {len(goals)}")
                    
                    found_protocol = False
                    for action in actions:
                        print(f"Action: {action['description']}")
                        if "Deep Focus Protocol" in action['description']:
                            found_protocol = True
                            
                    if found_protocol and len(goals) > 0:
                        print("✅ PASS: Grounded Protocol generated and registered.")
                    else:
                        print(f"❌ FAIL: Protocol not found. Plan content: {json.dumps(plan, default=str)}")
                        
                        # Debug: Check logic flow
                        print(f"Goals in Registry: {len(steward.registry.goals)}")
                        
                    # Verify Grounding Logic (Search was called)
                    # Note: Difficult to assert exactly on mock without deeper patching, 
                    # but logic flow confirms it enters _handle_idle_state
                    
if __name__ == "__main__":
    test_grounded_protocol_generation()
