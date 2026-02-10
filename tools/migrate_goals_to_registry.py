"""
Migrate legacy event-sourced goals into canonical GoalRegistry.

Default mode is dry-run.
"""
import argparse
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event_sourcing import rebuild_state  # noqa: E402
from core.goal_service import GoalService  # noqa: E402
from core.objective_engine.models import GoalLayer, GoalSource, GoalState, ObjectiveNode  # noqa: E402
from core.objective_engine.registry import GoalRegistry, REGISTRY_PATH  # noqa: E402


def _to_layer(horizon: Optional[str]) -> GoalLayer:
    value = (horizon or "goal").strip().lower()
    if value == "vision":
        return GoalLayer.VISION
    if value in {"milestone", "objective"}:
        return GoalLayer.OBJECTIVE
    return GoalLayer.GOAL


def _to_state(status: object) -> GoalState:
    raw = getattr(status, "value", status)
    value = str(raw or "").strip().lower()
    if value == "pending_confirm":
        return GoalState.VISION_PENDING_CONFIRMATION
    if value == "completed":
        return GoalState.COMPLETED
    if value == "abandoned":
        return GoalState.ARCHIVED
    if value == "blocked":
        return GoalState.BLOCKED
    return GoalState.ACTIVE


def _to_source(source: Optional[str]) -> GoalSource:
    raw = (source or "").strip().lower()
    if raw in {"top_down", "system", "user_input"}:
        return GoalSource(raw)
    if "ai" in raw:
        return GoalSource.SYSTEM
    return GoalSource.USER_INPUT


def _build_node(goal) -> ObjectiveNode:
    created_at = getattr(goal, "created_at", None)
    if created_at is not None and hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()

    return ObjectiveNode(
        id=getattr(goal, "id"),
        title=getattr(goal, "title", ""),
        description=getattr(goal, "description", ""),
        layer=_to_layer(getattr(goal, "horizon", "goal")),
        state=_to_state(getattr(goal, "status", "active")),
        source=_to_source(getattr(goal, "source", "")),
        parent_id=getattr(goal, "parent_id", None),
        created_at=created_at,
    )


def _backup_registry(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}.backup_{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def _print_counter(label: str, values: Iterable[str]) -> None:
    counter = Counter(values)
    if not counter:
        print(f"{label}: none")
        return
    print(f"{label}:")
    for key, count in sorted(counter.items(), key=lambda x: x[0]):
        print(f"  - {key}: {count}")


def migrate(apply: bool = False, update_existing: bool = False) -> int:
    state = rebuild_state()
    legacy_goals = state.get("goals", [])
    tasks = state.get("tasks", [])
    registry = GoalRegistry()
    service = GoalService(registry=registry)

    existing_nodes = {n.id: n for n in service.list_nodes()}
    migrated: List[ObjectiveNode] = []
    updated = 0
    skipped_existing = 0
    skipped_invalid = 0

    for goal in legacy_goals:
        goal_id = getattr(goal, "id", None)
        title = getattr(goal, "title", None)
        if not goal_id or not title:
            skipped_invalid += 1
            continue

        node = _build_node(goal)
        if goal_id in existing_nodes:
            if not update_existing:
                skipped_existing += 1
                continue
            existing = existing_nodes[goal_id]
            existing.title = node.title
            existing.description = node.description
            existing.layer = node.layer
            existing.state = node.state
            existing.source = node.source
            existing.parent_id = node.parent_id
            existing.updated_at = datetime.now().isoformat()
            migrated.append(existing)
            updated += 1
            continue

        migrated.append(node)

    future_node_ids = set(existing_nodes.keys()) | {n.id for n in migrated}
    missing_task_links = [t.id for t in tasks if getattr(t, "goal_id", None) not in future_node_ids]

    print("=== Goal Migration Report ===")
    print(f"legacy goals: {len(legacy_goals)}")
    print(f"registry goals before: {len(existing_nodes)}")
    print(f"to create: {len(migrated) - updated}")
    print(f"to update: {updated}")
    print(f"skipped existing: {skipped_existing}")
    print(f"skipped invalid: {skipped_invalid}")
    _print_counter("layers (candidate)", [n.layer.value for n in migrated])
    _print_counter("states (candidate)", [n.state.value for n in migrated])
    print(f"tasks missing goal linkage after migration: {len(missing_task_links)}")
    if missing_task_links:
        print(f"  sample task ids: {missing_task_links[:10]}")

    if not apply:
        print("\n[dry-run] no files changed")
        return 0

    backup = _backup_registry(REGISTRY_PATH)
    if backup:
        print(f"[backup] {backup}")

    for node in migrated:
        if node.id in existing_nodes and update_existing:
            registry.update_node(node)
        elif node.id not in existing_nodes:
            registry.add_node(node)

    print(f"[done] registry updated: {REGISTRY_PATH}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy goals to GoalRegistry.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply migration changes (default is dry-run)",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="update existing registry nodes when IDs match",
    )
    args = parser.parse_args()
    raise SystemExit(migrate(apply=args.apply, update_existing=args.update_existing))


if __name__ == "__main__":
    main()
