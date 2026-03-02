import requests
import json
import time

try:
    print("Triggering Brain Cycle...")
    response = requests.post("http://localhost:8001/api/v1/sys/cycle")
    response.raise_for_status()
    
    data = response.json()
    print("Response Status:", response.status_code)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    actions = data.get("generated_actions", [])
    if actions:
        print(f"\n✅ Generated {len(actions)} actions.")
        for action in actions:
            print(f"- [{action.get('priority')}] {action.get('description')}")
            
        # Check if it looks like a BHB task
        if any("bhb" in a.get("id", "").lower() or "better human" in str(a.get("metadata", {})).lower() for a in actions):
             print("\n✨ Verification SUCCEEDED: BHB task detected.")
        else:
             print("\n⚠️ Verification WARNING: Actions generated but might not be BHB specific.")
    else:
        print("\n❌ Verification FAILED: No actions generated (System still idle?).")

except Exception as e:
    print(f"Error: {e}")
