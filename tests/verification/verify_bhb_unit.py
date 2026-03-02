import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.steward import Steward

def test_bhb_logic():
    print("Testing BHB Engagement Logic...")
    
    # Mock State (Not cold start)
    mock_state = {
        "identity": {"name": "Test User", "occupation": "Tester"},
        "metrics": {"energy": "high"},
        "goals": [], # No active goals to force idle
        "time_state": {"current_date": "2026-01-30"}
    }
    
    steward = Steward(mock_state)
    
    # Directly call the method we want to test
    print("Invoking _handle_idle_state()...")
    actions = steward._handle_idle_state()
    
    print(f"\nGenerated {len(actions)} actions:")
    for action in actions:
        print(f"ID: {action.get('id')}")
        print(f"Desc: {action.get('description')}")
        print(f"Priority: {action.get('priority')}")
        print("-" * 20)
        
    # Validation
    if len(actions) > 0:
        desc = actions[0].get("description", "")
        if "BHB" in str(actions[0].get("metadata", {}).get("source", "")) or "better human" in desc.lower() or "🌱" in desc:
             print("\n✅ Verification SUCCESS: BHB Logic returned a valid engagement task.")
        else:
             print("\n⚠️ Verification WARNING: Returned action might be a fallback safety net.")
             print(f"Description was: {desc}")
    else:
        print("\n❌ Verification FAILED: No actions returned.")

if __name__ == "__main__":
    try:
        test_bhb_logic()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()
