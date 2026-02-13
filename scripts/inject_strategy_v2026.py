import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.event_sourcing import append_event  # noqa: E402
from core.objective_engine.models import GoalLayer, GoalSource, GoalState, ObjectiveNode  # noqa: E402
from core.objective_engine.registry import GoalRegistry  # noqa: E402
from core.paths import DATA_DIR  # noqa: E402

DATA_DIR.mkdir(parents=True, exist_ok=True)


def inject_strategy():
    print("Injecting 2026 life strategy...")

    append_event(
        {
            "type": "identity_updated",
            "payload": {
                "age": 29,
                "occupation": "Backend/AI Engineer (Transitioning)",
                "city": "Unknown (Remote Goal)",
            },
            "timestamp": datetime.now().isoformat(),
        }
    )

    append_event(
        {
            "type": "money_changed",
            "delta": 30000,
            "timestamp": datetime.now().isoformat(),
        }
    )

    append_event(
        {
            "type": "constraints_updated",
            "payload": {
                "work_hours": ["07:30-12:30", "13:30-17:30", "18:00-19:00"],
                "health_limits": ["07:00-07:30 Exercise", "23:00 Sleep"],
            },
            "timestamp": datetime.now().isoformat(),
        }
    )

    append_event(
        {
            "type": "habit_detected",
            "habit": {
                "pattern": "Deep Work Block (07:30-12:30)",
                "confidence": 1.0,
                "source": "strategy_injection",
            },
            "timestamp": datetime.now().isoformat(),
        }
    )
    print("State events appended.")

    registry = GoalRegistry()

    vision = ObjectiveNode(
        id="vis_2026_freedom",
        title="2028 Tech Nomad Strategy",
        description=(
            "Annual income 800k+ (remote/USD), 500k cash buffer, "
            "reproducible monetization system."
        ),
        layer=GoalLayer.VISION,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        deadline="2028-12-31",
    )
    registry.add_node(vision)
    append_event({"type": "goal_added", "goal": asdict(vision)})
    print(f"Created vision: {vision.title}")

    objective = ObjectiveNode(
        id="obj_2026_h1_transition",
        title="2026 H1: Basic Transition to Remote",
        description="Secure remote contracts via Upwork/Toptal and improve Python/Go/AI stack.",
        layer=GoalLayer.OBJECTIVE,
        parent_id=vision.id,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        deadline="2026-06-30",
        estimated_hours=1000,
    )
    registry.add_node(objective)
    append_event({"type": "goal_added", "goal": asdict(objective)})
    print(f"Created objective: {objective.title}")

    goal = ObjectiveNode(
        id="goal_week1_setup",
        title="Week 1: Infrastructure and Market Entry",
        description="Set up profiles, portfolio folders, and apply for initial jobs.",
        layer=GoalLayer.GOAL,
        parent_id=objective.id,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        goal_type="L1_SUBSTRATE",
        deadline=datetime.now().strftime("%Y-%m-%d"),
        sub_tasks=[
            {
                "id": "t_setup_folders",
                "description": (
                    "Create folders: "
                    "2026_Income_Leap/{Profile,Portfolio,Applications,Learning}"
                ),
                "estimated_time": 15,
                "difficulty": 1,
            },
            {
                "id": "t_polish_accounts",
                "description": "Register/polish GitHub, LinkedIn, Upwork, Arc.dev accounts",
                "estimated_time": 120,
                "difficulty": 2,
            },
            {
                "id": "t_update_bio",
                "description": "Update profile bio for remote backend positioning",
                "estimated_time": 15,
                "difficulty": 1,
            },
            {
                "id": "t_apply_daily",
                "description": "Submit 5 initial Upwork proposals",
                "estimated_time": 60,
                "difficulty": 3,
            },
        ],
    )
    registry.add_node(goal)
    append_event({"type": "goal_added", "goal": asdict(goal)})
    print(f"Created goal: {goal.title}")

    print("Strategy injection complete. Restart `main.py` to see the new plan.")


if __name__ == "__main__":
    inject_strategy()
