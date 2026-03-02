import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.bootstrap import get_bootstrap_tasks

def test_manual_bootstrap():
    print("--- Testing Dynamic Bootstrap (Empty State) ---")
    
    # Mock Empty State
    mock_state = {
        "identity": {},
        "time_state": {},
        "goals": []
    }
    
    print(f"Input State: {json.dumps(mock_state, indent=2, ensure_ascii=False)}")
    
    tasks = get_bootstrap_tasks(mock_state)
    
    print("\n--- Generated Tasks ---")
    print(json.dumps(tasks, indent=2, ensure_ascii=False))
    print(f"\n📊 问题数量: {len(tasks)}")
    
    if len(tasks) > 0 and tasks[0].get("id"):
        print("✅ Verification Successful: Tasks generated.")
    else:
        print("❌ Verification Failed: No tasks or invalid format.")


def test_partial_state():
    print("\n\n--- Testing Dynamic Bootstrap (Partial State) ---")
    
    # Mock Partial State - identity exists, goals is empty
    mock_state = {
        "identity": {
            "occupation": "软件工程师",
            "city": "北京"
        },
        "time_state": {"current_date": "2026-01-29"},
        "goals": [],
        "constraints": {}
    }
    
    print(f"Input State: {json.dumps(mock_state, indent=2, ensure_ascii=False)}")
    
    from core.bootstrap import get_bootstrap_tasks
    tasks = get_bootstrap_tasks(mock_state)
    
    print("\n--- Generated Tasks ---")
    print(json.dumps(tasks, indent=2, ensure_ascii=False))
    print(f"\n📊 问题数量: {len(tasks)}")
    
    # Expect fewer questions since identity is filled
    if len(tasks) < 5:
        print("✅ Verification Successful: Reduced questions for partial state.")
    else:
        print("⚠️ Warning: Still generating too many questions for partial state.")


if __name__ == "__main__":
    test_manual_bootstrap()
    test_partial_state()
