"""
Event Sourcing Engine for AI Life OS.

This module implements the core event sourcing logic:
- apply_event: Pure function to apply an event to state
- rebuild_state: Reconstruct state from event log
- append_event: Append new event to the log
"""
import json
import logging
from datetime import datetime, date
from uuid import uuid4
from typing import Any, Dict

# Core Data Models
from core.models import UserProfile, Goal, Task, Execution, GoalStatus, TaskStatus
from core.paths import DATA_DIR

# Data file paths
EVENT_LOG_PATH = DATA_DIR / "event_log.jsonl"
STATE_SNAPSHOT_PATH = DATA_DIR / "character_state.json"

logger = logging.getLogger("event_sourcing")

EVENT_SCHEMA_VERSION = "1.0"
REQUIRED_EVENT_FIELDS = ("type", "timestamp", "schema_version", "event_id")

# --- Initial State Structure ---

def get_initial_state() -> Dict[str, Any]:
    """
    Return the initial empty state structure following new models.
    """
    return {
        "profile": UserProfile(),
        # Compatibility view for modules/tests that still read legacy keys.
        "identity": {},
        "rhythm": {},
        "ongoing": {"active_tasks": []},
        "time_state": {"current_date": "", "previous_date": ""},
        "goals": [], # List[Goal]
        "tasks": [], # List[Task]
        "executions": [], # List[Execution]
        "system": {
            "last_active": None,
            "version": "2.0"
        }
    }

# --- Event Handlers ---

def apply_event(state: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure function: Apply a single event to state and return new state.
    """
    event_type = event.get("type")
    payload = event.get("payload", {})
    timestamp = event.get("timestamp")

    # --- Profile Events ---

    if event_type == "profile_updated":
        # payload: { "field": "occupation", "value": "coder" }
        field_name = payload.get("field")
        value = payload.get("value")
        if hasattr(state["profile"], field_name):
            setattr(state["profile"], field_name, value)
        if field_name:
            state.setdefault("identity", {})
            state["identity"][field_name] = value

    elif event_type == "onboarding_completed":
        state["profile"].onboarding_completed = True

    elif event_type == "preferences_updated":
        state["profile"].preferences.update(payload.get("preferences", {}))

    # --- Goal Events ---

    elif event_type == "goal_created":
        # payload: { "goal": {...} }
        goal_data = payload.get("goal")
        if goal_data:
            goal = Goal(**goal_data)
            # Convert status string to Enum
            if isinstance(goal.status, str):
                goal.status = GoalStatus(goal.status)
            # Convert deadline string to date
            if goal.deadline and isinstance(goal.deadline, str):
                try:
                    goal.deadline = date.fromisoformat(goal.deadline)
                except ValueError:
                    pass
            state["goals"].append(goal)

    elif event_type == "goal_updated":
        # payload: { "id": "...", "updates": {...} }
        goal_id = payload.get("id")
        updates = payload.get("updates", {})
        for goal in state["goals"]:
            if goal.id == goal_id:
                for k, v in updates.items():
                    if hasattr(goal, k):
                        if k == "status" and isinstance(v, str):
                            v = GoalStatus(v)
                        # Handle date updates if any
                        if k == "deadline" and isinstance(v, str):
                            try:
                                v = date.fromisoformat(v)
                            except ValueError:
                                pass
                        setattr(goal, k, v)
                break

    elif event_type == "goal_confirmed":
        # payload: { "id": "..." }
        goal_id = payload.get("id")
        for goal in state["goals"]:
            if goal.id == goal_id:
                goal.status = GoalStatus.ACTIVE
                goal.confirmed_at = timestamp
                break

    # --- Task Events ---

    elif event_type == "task_created":
        # payload: { "task": {...} }
        task_data = payload.get("task")
        if task_data:
            task = Task(**task_data)
            if isinstance(task.status, str):
                task.status = TaskStatus(task.status)
            # Convert scheduled_date string to date
            if hasattr(task, 'scheduled_date') and isinstance(task.scheduled_date, str):
                try:
                    task.scheduled_date = date.fromisoformat(task.scheduled_date)
                except ValueError:
                    pass
            state["tasks"].append(task)

    elif event_type == "task_updated":
        task_id = payload.get("id")
        updates = payload.get("updates", {})
        for task in state["tasks"]:
            if task.id == task_id:
                for k, v in updates.items():
                    if hasattr(task, k):
                        if k == "status" and isinstance(v, str):
                            v = TaskStatus(v)
                        setattr(task, k, v)
                break

    # --- Execution Events ---

    elif event_type == "execution_started":
        # payload: { "execution": {...} }
        exec_data = payload.get("execution")
        if exec_data:
            execution = Execution(**exec_data)
            state["executions"].append(execution)

    elif event_type == "execution_completed":
        exec_id = payload.get("id")
        outcome = payload.get("outcome")
        completed_at = payload.get("completed_at")
        for execution in state["executions"]:
            if execution.id == exec_id:
                execution.outcome = outcome
                execution.completed_at = completed_at
                break

    elif event_type == "time_tick":
        state["time_state"] = {
            "current_date": event.get("date", ""),
            "previous_date": event.get("previous_date", ""),
        }

    return state

# --- Core Functions ---

def rebuild_state() -> Dict[str, Any]:
    """
    Rebuild state from event log.
    """
    state = get_initial_state()

    if not EVENT_LOG_PATH.exists():
        return state

    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                state = apply_event(state, event)
            except Exception as e:
                logger.error(f"Failed to process event: {line[:100]}... Error: {e}")
                continue

    return state

def validate_event_shape(event: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """
    Validate event shape and return validation details.

    Args:
        event: Event dictionary
        strict: If True, all required fields are mandatory.
            If False, only `type` and `timestamp` are mandatory (legacy-compatible).
    """
    missing = []
    required = REQUIRED_EVENT_FIELDS if strict else ("type", "timestamp")
    for field in required:
        if not event.get(field):
            missing.append(field)
    return {"valid": not missing, "missing": missing}


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize an event to the canonical shape.
    """
    normalized = dict(event)
    normalized.setdefault("timestamp", datetime.now().isoformat())
    normalized.setdefault("schema_version", EVENT_SCHEMA_VERSION)
    normalized.setdefault("event_id", f"evt_{uuid4().hex[:12]}")
    return normalized


def append_event(event: Dict[str, Any]) -> None:
    """
    Append an event to the event log.
    After append: time_tick -> create_snapshot(force=True); else -> create_snapshot() if interval.
    """
    normalized_event = normalize_event(event)

    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(normalized_event, ensure_ascii=False, default=str) + "\n")

    from core.snapshot_manager import create_snapshot, should_create_snapshot
    if normalized_event.get("type") == "time_tick":
        create_snapshot(force=True)
    elif should_create_snapshot():
        create_snapshot()

