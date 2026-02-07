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
from core.event_sourcing import append_event, rebuild_state

def inject_strategy():
    print("🚀 Ingesting 2026 Life Strategy...")
    
    # 1. Update State (Identity, Inventory, Constraints)
    print("📝 Updating Character State...")
    
    # Identity Update
    append_event({
        "type": "identity_updated",
        "payload": {
            "age": 29,
            "occupation": "Backend/AI Engineer (Transitioning)",
            "city": "Unknown (Remote Goal)"
        },
        "timestamp": datetime.now().isoformat()
    })
    
    # Inventory Update
    append_event({
        "type": "money_changed", # Calculated delta to reach 30000
        "delta": 30000, # Assuming start from near 0 or reset
        "timestamp": datetime.now().isoformat()
    })
    
    # Constraints Update (Schedule)
    append_event({
        "type": "constraints_updated",
        "payload": {
            "work_hours": ["07:30-12:30", "13:30-17:30", "18:00-19:00"],
            "health_limits": ["07:00-07:30 Exercise", "23:00 Sleep"]
        },
        "timestamp": datetime.now().isoformat()
    })
    
    # Rhythm/Habit Injection (Manual Event)
    # Start with a strong "morning routine" habit
    append_event({
        "type": "habit_detected", # Custom event type if supported, otherwise just rely on goal
        "habit": {
            "pattern": "Deep Work Block (07:30-12:30)",
            "confidence": 1.0,
            "source": "strategy_injection"
        },
        "timestamp": datetime.now().isoformat()
    })
    
    print("✅ State events appended.")

    # 2. Inject Goals
    registry = GoalRegistry()
    
    # A. Vision (2026-2028)
    vision = ObjectiveNode(
        id="vis_2026_freedom",
        title="2028 Tech Nomad Strategy",
        description="Annual Income 800k+ (Remote/USD), 500k Cash Buffer, Reproducible Monetization System.",
        layer=GoalLayer.VISION,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        deadline="2028-12-31"
    )
    registry.add_node(vision)
    append_event({"type": "goal_added", "goal": asdict(vision)})
    print(f"✅ Created Vision: {vision.title}")
    
    # B. Objective (2026 H1)
    objective = ObjectiveNode(
        id="obj_2026_h1_transition",
        title="2026 H1: Basic Transition to Remote",
        description="Secure consistent remote contracts via Upwork/Toptal. Mastering Python/Go/AI Stack.",
        layer=GoalLayer.OBJECTIVE,
        parent_id=vision.id,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        deadline="2026-06-30",
        estimated_hours=1000
    )
    registry.add_node(objective)
    append_event({"type": "goal_added", "goal": asdict(objective)})
    print(f"✅ Created Objective: {objective.title}")
    
    # C. Goal (Immediate - Week 1)
    # "Today" actions are mapped to a Substrate Goal
    goal = ObjectiveNode(
        id="goal_week1_setup",
        title="Week 1: Infrastructure & Market Entry",
        description="Setup profiles, portfolio folders, and apply for initial jobs.",
        layer=GoalLayer.GOAL,
        parent_id=objective.id,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        goal_type="L1_SUBSTRATE",
        deadline=datetime.now().strftime("%Y-%m-%d"), # Due today for urgency
        sub_tasks=[
            {
                "id": "t_setup_folders",
                "description": "Create folders: 2026_Income_Leap/{Profile, Portfolio, Applications, Learning}",
                "estimated_time": 15,
                "difficulty": 1
            },
            {
                "id": "t_polish_accounts",
                "description": "Register/Polish GitHub, LinkedIn, Upwork, Arc.dev accounts",
                "estimated_time": 120,
                "difficulty": 2
            },
            {
                "id": "t_update_bio",
                "description": "Update Bio to: 'Remote Backend Engineer with strong Python/Go skills...'",
                "estimated_time": 15,
                "difficulty": 1
            },
            {
                "id": "t_apply_daily",
                "description": "Apply to 5 Upwork proposals (Initial Batch)",
                "estimated_time": 60,
                "difficulty": 3
            }
        ]
    )
    registry.add_node(goal)
    append_event({"type": "goal_added", "goal": asdict(goal)})
    print(f"✅ Created Goal: {goal.title}")

    print("\n🎉 Strategy Injection Complete. Please restart 'main.py' to see the new plan.")

if __name__ == "__main__":
    inject_strategy()
