import sys
from pathlib import Path
import logging
from datetime import date

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import setup_logging
from core.models import Goal, UserProfile, GoalStatus
from core.goal_generator import GoalGenerator
from core.task_decomposer import TaskDecomposer
from core.blueprint import Blueprint
from core.event_sourcing import append_event, rebuild_state

# Setup simple logging
logging.basicConfig(level=logging.INFO)

def main():
    print(">>> 1. Creating a Mock Goal...")
    # Simulate a goal that came from generation
    goal = Goal(
        id="debug_goal_001",
        title="Debug: Learn Rust",
        description="Learn Rust programming language basics.",
        source="debug_script",
        status=GoalStatus.PENDING_CONFIRM,
        resource_description="The Rust Book",
        target_level="Write a CLI tool",
        tags=["Career", "Tech"]
    )
    
    print(f"Goal: {goal.title}")
    
    print("\n>>> 2. Running TaskDecomposer...")
    decomposer = TaskDecomposer()
    # Force decomposer to run
    tasks = decomposer.decompose_goal(goal, start_date=date.today())
    
    print(f"Generated {len(tasks)} tasks.")
    
    if not tasks:
        print("ERROR: No tasks generated! Check LLM logs.")
        return

    for t in tasks:
        print(f" - [{t.scheduled_date}] {t.description} (Status: {t.status})")
        
    print("\n>>> 3. Simulating Confirm API Event Sourcing...")
    # Append goal_created
    goal.status = GoalStatus.ACTIVE
    append_event({"type": "goal_created", "payload": {"goal": goal.__dict__}})
    
    # Append task_created
    for t in tasks:
       append_event({"type": "task_created", "payload": {"task": t.__dict__}}) 
       
    print(">>> Events appended. Rebuilding state to verify...")
    state = rebuild_state()
    
    found_goal = next((g for g in state["goals"] if g.id == goal.id), None)
    print(f"Goal found in state: {found_goal is not None}")
    
    found_tasks = [t for t in state["tasks"] if t.goal_id == goal.id]
    print(f"Tasks found in state: {len(found_tasks)}")
    
    if len(found_tasks) > 0:
        print("SUCCESS: Flow is working on backend level.")
    else:
        print("FAILURE: State reconstruction incorrect.")

if __name__ == "__main__":
    main()
