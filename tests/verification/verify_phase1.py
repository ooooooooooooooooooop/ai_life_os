"""
Verification script for Phase 1: Core Infrastructure.
Tests Models, Event Sourcing, and Blueprint Engine.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.models import UserProfile, Goal, GoalStatus, Task, TaskStatus
from datetime import date, datetime
from core.event_sourcing import get_initial_state, apply_event
from core.blueprint import Blueprint

def test_models():
    print("\n--- Testing Models ---")
    u = UserProfile(occupation="Coder", daily_hours="4h")
    print(f"UserProfile created: {u}")
    
    g = Goal(
        id="g1", 
        title="Learn Rust", 
        description="Master Rust ownership", 
        source="ai", 
        status=GoalStatus.PENDING_CONFIRM
    )
    print(f"Goal created: {g}")
    assert g.status == GoalStatus.PENDING_CONFIRM

def test_event_sourcing():
    print("\n--- Testing Event Sourcing ---")
    state = get_initial_state()
    print("Initial state initialized.")
    
    # Simulate events
    events = [
        {
            "type": "profile_updated",
            "payload": {"field": "occupation", "value": "AI Engineer"},
            "timestamp": datetime.now().isoformat()
        },
        {
            "type": "goal_created",
            "payload": {
                "goal": {
                    "id": "g1",
                    "title": "Learn AI",
                    "description": "Deep dive into LLMs",
                    "source": "ai",
                    "status": "pending_confirm"
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    for evt in events:
        state = apply_event(state, evt)
        
    print(f"State after events: Profile occupation={state['profile'].occupation}, Goals count={len(state['goals'])}")
    assert state['profile'].occupation == "AI Engineer"
    assert len(state['goals']) == 1
    assert state['goals'][0].title == "Learn AI"
    print("Event sourcing check passed.")

def test_blueprint():
    print("\n--- Testing Blueprint ---")
    bp = Blueprint()
    
    context = UserProfile(daily_hours="5h")
    g1 = Goal(id="1", title="A", description="Short", source="ai", status=GoalStatus.PENDING_CONFIRM)
    g2 = Goal(id="2", title="B", description="A very long description representing a detailed and valuable goal.", source="ai", status=GoalStatus.PENDING_CONFIRM)
    
    # Mock evaluate
    score1 = bp.evaluate(g1, context)
    score2 = bp.evaluate(g2, context)
    
    print(f"Goal 1 Score: {score1.score} (Passed: {score1.passed})")
    print(f"Goal 2 Score: {score2.score} (Passed: {score2.passed})")
    
    # Rank
    ranked = bp.filter_and_rank([g1, g2], context)
    print(f"Ranked: {[g.title for g, s in ranked]}")
    assert ranked[0][0].id == "2" # g2 shoud be higher due to heuristic
    print("Blueprint check passed.")

if __name__ == "__main__":
    try:
        test_models()
        test_event_sourcing()
        test_blueprint()
        print("\n✅ Phase 1 Verification SUCCESS!")
    except Exception as e:
        print(f"\n❌ Phase 1 Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
