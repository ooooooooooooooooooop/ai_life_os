"""
Canonical goal domain service.

Unifies goal writes/reads around GoalRegistry as the single source of truth.
"""
import re
import uuid
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.blueprint import Blueprint
from core.event_sourcing import append_event, rebuild_state
from core.goal_generator import GoalGenerator
from core.models import Goal as DecompositionGoal
from core.models import GoalStatus, UserProfile
from core.objective_engine.models import GoalLayer, GoalSource, GoalState, ObjectiveNode
from core.objective_engine.registry import GoalRegistry
from core.task_decomposer import TaskDecomposer


class GoalService:
    """Application service for canonical goal operations."""

    def __init__(self, registry: Optional[GoalRegistry] = None):
        self.registry = registry or GoalRegistry()

    # ---------------------------------------------------------------------
    # Mapping helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def id_prefix_for_layer(layer: GoalLayer) -> str:
        mapping = {
            GoalLayer.VISION: "vision",
            GoalLayer.OBJECTIVE: "obj",
            GoalLayer.GOAL: "g",
        }
        return mapping.get(layer, "g")

    @staticmethod
    def source_from_string(source: Optional[str]) -> GoalSource:
        if not source:
            return GoalSource.USER_INPUT
        try:
            return GoalSource(source)
        except ValueError:
            lowered = source.lower()
            if "system" in lowered or "ai" in lowered:
                return GoalSource.SYSTEM
            if "top" in lowered:
                return GoalSource.TOP_DOWN
            return GoalSource.USER_INPUT

    @staticmethod
    def layer_from_string(layer: Optional[str]) -> GoalLayer:
        mapping = {
            "vision": GoalLayer.VISION,
            "objective": GoalLayer.OBJECTIVE,
            "goal": GoalLayer.GOAL,
        }
        return mapping.get((layer or "goal").lower(), GoalLayer.GOAL)

    @staticmethod
    def decomposition_horizon_from_layer(layer: GoalLayer) -> str:
        mapping = {
            GoalLayer.VISION: "vision",
            GoalLayer.OBJECTIVE: "milestone",
            GoalLayer.GOAL: "goal",
        }
        return mapping.get(layer, "goal")

    @staticmethod
    def state_from_string(state: Optional[str]) -> GoalState:
        raw = str(state or "").strip().lower()
        mapping = {
            "draft": GoalState.DRAFT,
            "active": GoalState.ACTIVE,
            "vision_pending_confirmation": GoalState.VISION_PENDING_CONFIRMATION,
            "completed": GoalState.COMPLETED,
            "archived": GoalState.ARCHIVED,
            "blocked": GoalState.BLOCKED,
            "pending_confirm": GoalState.VISION_PENDING_CONFIRMATION,
            "abandoned": GoalState.ARCHIVED,
        }
        return mapping.get(raw, GoalState.ACTIVE)

    @staticmethod
    def next_layer(layer: GoalLayer) -> GoalLayer:
        if layer == GoalLayer.VISION:
            return GoalLayer.OBJECTIVE
        if layer == GoalLayer.OBJECTIVE:
            return GoalLayer.GOAL
        return GoalLayer.GOAL

    # ---------------------------------------------------------------------
    # Serialization helpers
    # ---------------------------------------------------------------------
    def node_to_dict(self, node: ObjectiveNode) -> Dict[str, Any]:
        data = asdict(node)
        data["layer"] = node.layer.value
        data["state"] = node.state.value
        data["source"] = node.source.value
        return data

    def _node_to_decomposition_goal(
        self,
        node: ObjectiveNode,
        extras: Optional[Dict[str, Any]] = None,
    ) -> DecompositionGoal:
        extras = extras or {}
        status_value = GoalStatus.ACTIVE.value
        if node.state == GoalState.VISION_PENDING_CONFIRMATION:
            status_value = GoalStatus.PENDING_CONFIRM.value
        elif node.state == GoalState.COMPLETED:
            status_value = GoalStatus.COMPLETED.value
        elif node.state == GoalState.ARCHIVED:
            status_value = GoalStatus.ABANDONED.value
        try:
            status = GoalStatus(status_value)
        except ValueError:
            status = GoalStatus.ACTIVE

        return DecompositionGoal(
            id=node.id,
            title=extras.get("title", node.title),
            description=extras.get("description", node.description),
            source=extras.get("source", node.source.value),
            status=status,
            parent_id=node.parent_id,
            horizon=self.decomposition_horizon_from_layer(node.layer),
            depends_on=extras.get("depends_on", []),
            resource_description=extras.get("resource_description", ""),
            target_level=extras.get("target_level", ""),
            tags=extras.get("tags", []),
        )

    # ---------------------------------------------------------------------
    # Event helpers
    # ---------------------------------------------------------------------
    def _emit_canonical_event(
        self,
        event_type: str,
        node: ObjectiveNode,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        append_event(
            {
                "type": event_type,
                "goal_id": node.id,
                "timestamp": datetime.now().isoformat(),
                "payload": payload or {"node": self.node_to_dict(node)},
            }
        )

    # ---------------------------------------------------------------------
    # Query operations
    # ---------------------------------------------------------------------
    def get_node(self, node_id: str) -> Optional[ObjectiveNode]:
        return self.registry.get_node(node_id)

    def require_node(self, node_id: str) -> ObjectiveNode:
        node = self.get_node(node_id)
        if not node:
            raise ValueError("Goal not found")
        return node

    def list_nodes(
        self,
        state: Optional[str] = None,
        layer: Optional[str] = None,
    ) -> List[ObjectiveNode]:
        nodes = self.registry.visions + self.registry.objectives + self.registry.goals
        if state:
            nodes = [n for n in nodes if n.state.value == state]
        if layer:
            nodes = [n for n in nodes if n.layer.value == layer]
        return sorted(nodes, key=lambda x: x.created_at or "")

    def list_visions(self) -> List[ObjectiveNode]:
        return self.list_nodes(layer=GoalLayer.VISION.value)

    def get_goal_tree(self, only_active: bool = True) -> List[Dict[str, Any]]:
        nodes = self.list_nodes()
        if only_active:
            nodes = [n for n in nodes if n.state == GoalState.ACTIVE]

        by_parent: Dict[Optional[str], List[ObjectiveNode]] = {}
        for node in nodes:
            by_parent.setdefault(node.parent_id, []).append(node)

        for bucket in by_parent.values():
            bucket.sort(key=lambda x: (x.created_at or "", x.id))

        def build(parent_id: Optional[str]) -> List[Dict[str, Any]]:
            children = []
            for item in by_parent.get(parent_id, []):
                d = self.node_to_dict(item)
                d["children"] = build(item.id)
                children.append(d)
            return children

        return build(None)

    # ---------------------------------------------------------------------
    # Command operations
    # ---------------------------------------------------------------------
    def create_vision(
        self,
        title: str,
        description: str = "",
        source: str = "user_input",
    ) -> ObjectiveNode:
        node = ObjectiveNode(
            id=self._new_id("vision"),
            title=title,
            description=description,
            layer=GoalLayer.VISION,
            state=GoalState.ACTIVE,
            source=self.source_from_string(source),
        )
        self.registry.add_node(node)
        self._emit_canonical_event("goal_registry_created", node)
        return node

    def create_node(
        self,
        title: str,
        description: str = "",
        layer: GoalLayer = GoalLayer.GOAL,
        state: GoalState = GoalState.ACTIVE,
        source: str = GoalSource.USER_INPUT.value,
        parent_id: Optional[str] = None,
        goal_type: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> ObjectiveNode:
        """
        Create a canonical objective node and always emit the standard registry event.
        """
        node = ObjectiveNode(
            id=node_id or self._new_id(self.id_prefix_for_layer(layer)),
            title=title,
            description=description,
            layer=layer,
            state=state,
            source=self.source_from_string(source),
            parent_id=parent_id,
            goal_type=goal_type,
        )
        self.registry.add_node(node)
        self._emit_canonical_event("goal_registry_created", node)
        return node

    def update_vision(
        self, vision_id: str, title: Optional[str] = None, description: Optional[str] = None
    ) -> ObjectiveNode:
        vision = self.require_node(vision_id)
        if vision.layer != GoalLayer.VISION:
            raise ValueError("Node is not a Vision")

        if title:
            vision.title = title
        if description:
            vision.description = description
        vision.updated_at = datetime.now().isoformat()
        self.registry.update_node(vision)

        self._emit_canonical_event("goal_registry_updated", vision)
        return vision

    def confirm_candidate_goal(self, goal_data: Dict[str, Any]) -> Tuple[ObjectiveNode, int]:
        goal_id = goal_data.get("id") or self._new_id("g")
        existing = self.get_node(goal_id)
        layer = self.layer_from_string(goal_data.get("layer"))

        node = existing or ObjectiveNode(
            id=goal_id,
            title=goal_data.get("title", "Untitled Goal"),
            description=goal_data.get("description", ""),
            layer=layer,
            state=GoalState.ACTIVE,
            source=self.source_from_string(goal_data.get("source", "ai_generated")),
            parent_id=goal_data.get("parent_id"),
        )

        node.title = goal_data.get("title", node.title)
        node.description = goal_data.get("description", node.description)
        node.layer = self.layer_from_string(goal_data.get("layer", node.layer.value))
        node.state = GoalState.ACTIVE
        node.source = self.source_from_string(goal_data.get("source", node.source.value))
        node.parent_id = goal_data.get("parent_id", node.parent_id)
        node.updated_at = datetime.now().isoformat()

        if existing:
            self.registry.update_node(node)
            self._emit_canonical_event("goal_registry_updated", node)
        else:
            self.registry.add_node(node)
            self._emit_canonical_event("goal_registry_created", node)

        tasks_created = 0
        if node.layer == GoalLayer.GOAL:
            decomposed = self._node_to_decomposition_goal(node, goal_data)
            tasks_created = self._decompose_to_tasks(decomposed)
        return node, tasks_created

    def confirm_goal(self, goal_id: str, strict_pending: bool = True) -> ObjectiveNode:
        node = self.require_node(goal_id)
        if strict_pending and node.state != GoalState.VISION_PENDING_CONFIRMATION:
            raise ValueError(f"Goal is not pending confirmation (current: {node.state.value})")

        node.state = GoalState.ACTIVE
        node.updated_at = datetime.now().isoformat()
        self.registry.update_node(node)

        self._emit_canonical_event("goal_registry_confirmed", node)
        return node

    def reject_goal(self, goal_id: str) -> ObjectiveNode:
        node = self.require_node(goal_id)
        node.state = GoalState.ARCHIVED
        node.updated_at = datetime.now().isoformat()
        self.registry.update_node(node)

        self._emit_canonical_event("goal_registry_rejected", node)
        return node

    def archive_goal(self, goal_id: str) -> ObjectiveNode:
        node = self.require_node(goal_id)
        node.state = GoalState.ARCHIVED
        node.updated_at = datetime.now().isoformat()
        self.registry.update_node(node)

        self._emit_canonical_event("goal_registry_archived", node)
        return node

    def apply_feedback(
        self, goal_id: str, intent: str, extracted_reason: Optional[str] = None
    ) -> ObjectiveNode:
        node = self.require_node(goal_id)
        normalized = intent.strip().lower()

        if normalized == "complete":
            node.state = GoalState.COMPLETED
            node.success_count += 1
        elif normalized == "skip":
            node.skip_count += 1
        elif normalized == "blocked":
            node.state = GoalState.BLOCKED
            node.blocked_reason = extracted_reason
        elif normalized in {"defer", "partial"}:
            pass

        node.updated_at = datetime.now().isoformat()
        self.registry.update_node(node)

        self._emit_canonical_event(
            "goal_registry_feedback",
            node,
            payload={"intent": normalized, "reason": extracted_reason},
        )
        return node

    def apply_action(
        self,
        goal_id: str,
        action: str,
        reason: Optional[str] = None,
    ) -> ObjectiveNode:
        node = self.require_node(goal_id)
        normalized = action.strip().lower()

        if normalized == "complete":
            node.state = GoalState.COMPLETED
            node.success_count += 1
        elif normalized == "skip":
            node.skip_count += 1
        elif normalized == "start":
            node.state = GoalState.ACTIVE

        node.updated_at = datetime.now().isoformat()
        self.registry.update_node(node)

        self._emit_canonical_event(
            "goal_registry_action",
            node,
            payload={"action": normalized, "reason": reason},
        )
        return node

    # ---------------------------------------------------------------------
    # Goal generation and decomposition
    # ---------------------------------------------------------------------
    def generate_candidates(self, n: int = 3) -> List[Dict[str, Any]]:
        state = rebuild_state()
        profile = state.get("profile")
        if not isinstance(profile, UserProfile):
            profile = UserProfile()

        generator = GoalGenerator(Blueprint())
        candidates = generator.generate_candidates(profile, n=n)

        result = []
        for goal, score in candidates:
            result.append(
                {
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "layer": GoalLayer.GOAL.value,
                    "source": goal.source,
                    "resource_description": goal.resource_description,
                    "target_level": goal.target_level,
                    "tags": goal.tags,
                    "_score": score.score,
                }
            )
        return result

    def get_decomposition_questions(self, goal_id: str) -> List[Dict[str, Any]]:
        state = rebuild_state()
        profile = state.get("profile")
        if not isinstance(profile, UserProfile):
            profile = UserProfile()

        parent = self.require_node(goal_id)
        generator = GoalGenerator(Blueprint())
        return generator.get_feasibility_questions(
            self._node_to_decomposition_goal(parent),
            profile,
        )

    def get_decomposition_options(
        self, goal_id: str, context: Optional[Dict[str, Any]] = None, n: int = 3
    ) -> Dict[str, Any]:
        state = rebuild_state()
        profile = state.get("profile")
        if not isinstance(profile, UserProfile):
            profile = UserProfile()

        parent = self.require_node(goal_id)
        child_layer = self.next_layer(parent.layer)
        existing_titles = [
            x.title
            for x in self.list_nodes()
            if x.parent_id == goal_id and x.state == GoalState.ACTIVE
        ]

        generator = GoalGenerator(Blueprint())
        candidates = generator.decompose_to_children(
            self._node_to_decomposition_goal(parent),
            profile,
            n=n,
            context=context,
            existing_titles=existing_titles,
        )

        return {
            "action": "choose_option",
            "candidates": candidates,
            "layer": child_layer.value,
        }

    def create_decomposed_child(
        self,
        goal_id: str,
        selected_option: Optional[Dict[str, Any]] = None,
        custom_input: Optional[str] = None,
    ) -> Tuple[ObjectiveNode, int, bool]:
        parent = self.require_node(goal_id)
        child_layer = self.next_layer(parent.layer)

        title = ""
        description = ""
        if selected_option:
            title = self.normalize_title(selected_option.get("title", "Untitled Goal"))
            description = selected_option.get("description", "")
        elif custom_input:
            title = self.normalize_title(custom_input)
            description = "User-defined decomposed goal"

        if not title:
            raise ValueError("Empty goal title")

        active_siblings = [
            x
            for x in self.list_nodes()
            if x.parent_id == goal_id and x.state == GoalState.ACTIVE
        ]
        existing = next((x for x in active_siblings if x.title == title), None)
        if existing:
            return existing, 0, True

        child = ObjectiveNode(
            id=self._new_id("g"),
            title=title,
            description=description,
            layer=child_layer,
            state=GoalState.ACTIVE,
            source=GoalSource.TOP_DOWN,
            parent_id=goal_id,
            goal_type=parent.goal_type,
        )
        self.registry.add_node(child)

        if child.id not in parent.children_ids:
            parent.children_ids.append(child.id)
            parent.updated_at = datetime.now().isoformat()
            self.registry.update_node(parent)
            self._emit_canonical_event("goal_registry_updated", parent)

        self._emit_canonical_event("goal_registry_created", child)

        tasks_created = 0
        if child.layer == GoalLayer.GOAL:
            tasks_created = self._decompose_to_tasks(self._node_to_decomposition_goal(child))

        return child, tasks_created, False

    @staticmethod
    def normalize_title(title: str) -> str:
        pattern = r"^(?:Option|选项)\s*[0-9a-zA-Z一二三四五六七八九十IVXLCDM]+[:：\s\-\.]*"
        return re.sub(pattern, "", str(title or ""), flags=re.IGNORECASE).strip()

    def _decompose_to_tasks(self, goal: DecompositionGoal) -> int:
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose_goal(goal, start_date=date.today())
        for task in tasks:
            append_event({"type": "task_created", "payload": {"task": task.__dict__}})
        return len(tasks)
