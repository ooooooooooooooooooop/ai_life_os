import sys
import json
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure data directory exists
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

from core.objective_engine.registry import GoalRegistry
from core.objective_engine.models import ObjectiveNode, GoalLayer, GoalState, GoalSource
from core.event_sourcing import append_event

def inject_goal():
    print("🚀 Injecting initial goal: Implement Objective Engine...")
    
    registry = GoalRegistry()
    
    # Check if goal already exists to avoid duplicates
    existing_goals = [g for g in registry.goals if g.title == "Implement Objective Engine"]
    if existing_goals:
        print(f"⚠️ Goal 'Implement Objective Engine' already exists (ID: {existing_goals[0].id}). Skipping.")
        return

    # 1. Create Objective (Parent)
    # Check if parent objective exists first
    existing_objectives = [o for o in registry.objectives if o.title == "Build AI Life OS v2.0"]
    if existing_objectives:
        objective = existing_objectives[0]
        print(f"✅ Found existing Objective: {objective.title} ({objective.id})")
    else:
        objective = ObjectiveNode(
            id="obj_initial_setup",
            title="Build AI Life OS v2.0",
            description="Complete the core implementation of AI Life OS features.",
            layer=GoalLayer.OBJECTIVE,
            state=GoalState.ACTIVE,
            source=GoalSource.SYSTEM
        )
        registry.add_node(objective) # Persists to registry
        print(f"✅ Created Objective: {objective.title}")
        
        # Persist event
        append_event({
            "type": "goal_added",
            "goal": asdict(objective),
            "timestamp": datetime.now().isoformat()
        })
    
    # 2. Create Goal (Child)
    goal = ObjectiveNode(
        id="goal_implement_objective_engine",
        title="Implement Objective Engine",
        description="Implement the full objective engine including registry, models, and steward integration.",
        layer=GoalLayer.GOAL,
        parent_id=objective.id,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        goal_type="substrate", # Substrate = L1 Task
        deadline=datetime.now().strftime("%Y-%m-%d")
    )
    
    registry.add_node(goal) # Persists to registry
    print(f"✅ Created Goal: {goal.title}")
    
    # Persist event
    append_event({
        "type": "goal_added",
        "goal": asdict(goal),
        "timestamp": datetime.now().isoformat()
    })
    
    print("\n🎉 Injection complete! Please restart the 'main.py' process to see the new goal.")

if __name__ == "__main__":
    inject_goal()
