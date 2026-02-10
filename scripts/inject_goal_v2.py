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


def inject_goal():
    print("Injecting initial goal: Implement Objective Engine...")

    registry = GoalRegistry()

    existing_goals = [g for g in registry.goals if g.title == "Implement Objective Engine"]
    if existing_goals:
        print(f"Goal already exists (ID: {existing_goals[0].id}). Skipping.")
        return

    existing_objectives = [o for o in registry.objectives if o.title == "Build AI Life OS v2.0"]
    if existing_objectives:
        objective = existing_objectives[0]
        print(f"Found existing objective: {objective.title} ({objective.id})")
    else:
        objective = ObjectiveNode(
            id="obj_initial_setup",
            title="Build AI Life OS v2.0",
            description="Complete the core implementation of AI Life OS features.",
            layer=GoalLayer.OBJECTIVE,
            state=GoalState.ACTIVE,
            source=GoalSource.SYSTEM,
        )
        registry.add_node(objective)
        print(f"Created objective: {objective.title}")
        append_event(
            {
                "type": "goal_added",
                "goal": asdict(objective),
                "timestamp": datetime.now().isoformat(),
            }
        )

    goal = ObjectiveNode(
        id="goal_implement_objective_engine",
        title="Implement Objective Engine",
        description="Implement objective engine registry, models, and steward integration.",
        layer=GoalLayer.GOAL,
        parent_id=objective.id,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
        goal_type="substrate",
        deadline=datetime.now().strftime("%Y-%m-%d"),
    )

    registry.add_node(goal)
    print(f"Created goal: {goal.title}")

    append_event(
        {
            "type": "goal_added",
            "goal": asdict(goal),
            "timestamp": datetime.now().isoformat(),
        }
    )

    print("Injection complete. Restart `main.py` to see the new goal.")


if __name__ == "__main__":
    inject_goal()
