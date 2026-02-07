"""
GoalRegistry: in-memory store of Vision/Objective/Goal nodes with JSON persistence.
Path: data/goal_registry.json (aligned with tools/reset_system.py).
"""
from pathlib import Path
from typing import List, Optional
import json

from core.objective_engine.models import ObjectiveNode, GoalLayer, GoalState

DATA_DIR = Path(__file__).parent.parent.parent / "data"
REGISTRY_PATH = DATA_DIR / "goal_registry.json"


def _node_to_dict(n: ObjectiveNode) -> dict:
    d = {
        "id": n.id,
        "title": n.title,
        "description": n.description,
        "layer": n.layer.value,
        "state": n.state.value,
        "source": getattr(n.source, "value", str(n.source)),
        "parent_id": n.parent_id,
        "children_ids": n.children_ids,
        "goal_type": n.goal_type,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
        "deadline": n.deadline,
        "sub_tasks": n.sub_tasks,
        "success_count": n.success_count,
        "skip_count": n.skip_count,
        "blocked_reason": n.blocked_reason,
        "worthiness_score": n.worthiness_score,
        "urgency_score": n.urgency_score,
        "feasibility_score": n.feasibility_score,
        "estimated_hours": n.estimated_hours,
    }
    return d


def _dict_to_node(d: dict) -> ObjectiveNode:
    return ObjectiveNode(
        id=d["id"],
        title=d["title"],
        description=d.get("description", ""),
        layer=GoalLayer(d["layer"]),
        state=GoalState(d.get("state", "draft")),
        source=__source_from_str(d.get("source", "user_input")),
        parent_id=d.get("parent_id"),
        children_ids=d.get("children_ids", []),
        goal_type=d.get("goal_type"),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
        deadline=d.get("deadline"),
        sub_tasks=d.get("sub_tasks", []),
        success_count=d.get("success_count", 0),
        skip_count=d.get("skip_count", 0),
        blocked_reason=d.get("blocked_reason"),
        worthiness_score=d.get("worthiness_score", 0.0),
        urgency_score=d.get("urgency_score", 0.0),
        feasibility_score=d.get("feasibility_score", 1.0),
        estimated_hours=d.get("estimated_hours"),
    )


def __source_from_str(s: str):
    from core.objective_engine.models import GoalSource
    try:
        return GoalSource(s)
    except ValueError:
        return GoalSource.USER_INPUT


class GoalRegistry:
    """In-memory registry with JSON persistence at REGISTRY_PATH."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path if path is not None else REGISTRY_PATH
        self._nodes: dict[str, ObjectiveNode] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", data) if isinstance(data, dict) else data
            if not isinstance(nodes, list):
                nodes = []
            for d in nodes:
                n = _dict_to_node(d)
                self._nodes[n.id] = n
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"nodes": [_node_to_dict(n) for n in self._nodes.values()]}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def add_node(self, node: ObjectiveNode) -> None:
        self._nodes[node.id] = node
        self.save()

    def get_node(self, node_id: str) -> Optional[ObjectiveNode]:
        return self._nodes.get(node_id)

    def update_node(self, node: ObjectiveNode) -> None:
        self._nodes[node.id] = node
        self.save()

    @property
    def visions(self) -> List[ObjectiveNode]:
        return [n for n in self._nodes.values() if n.layer == GoalLayer.VISION]

    @property
    def objectives(self) -> List[ObjectiveNode]:
        return [n for n in self._nodes.values() if n.layer == GoalLayer.OBJECTIVE]

    @property
    def goals(self) -> List[ObjectiveNode]:
        return [n for n in self._nodes.values() if n.layer == GoalLayer.GOAL]
