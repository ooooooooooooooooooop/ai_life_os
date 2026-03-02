"""
Tests for Event Sourcing Core (current data model).
"""
import shutil
import unittest
from pathlib import Path
from tempfile import mkdtemp

import core.event_sourcing as es
from core.event_sourcing import apply_event, append_event, get_initial_state, rebuild_state
from core.models import GoalStatus, TaskStatus


class TestEventSourcing(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(mkdtemp())
        self.original_data_dir = es.DATA_DIR
        self.original_log_path = es.EVENT_LOG_PATH
        self.original_snapshot_path = es.STATE_SNAPSHOT_PATH

        es.DATA_DIR = self.test_dir
        es.EVENT_LOG_PATH = self.test_dir / "test_events.jsonl"
        es.STATE_SNAPSHOT_PATH = self.test_dir / "state.json"
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        es.DATA_DIR = self.original_data_dir
        es.EVENT_LOG_PATH = self.original_log_path
        es.STATE_SNAPSHOT_PATH = self.original_snapshot_path
        shutil.rmtree(self.test_dir)

    def test_initial_state(self):
        state = get_initial_state()
        self.assertIn("profile", state)
        self.assertIn("goals", state)
        self.assertIn("tasks", state)
        self.assertIn("executions", state)
        self.assertEqual(state["profile"].occupation, "")
        self.assertEqual(state["goals"], [])

    def test_append_and_rebuild_with_time_tick(self):
        append_event(
            {
                "type": "time_tick",
                "date": "2026-01-01",
                "previous_date": "",
                "timestamp": "2026-01-01T10:00:00",
            }
        )
        append_event(
            {
                "type": "profile_updated",
                "payload": {"field": "occupation", "value": "engineer"},
                "timestamp": "2026-01-01T10:05:00",
            }
        )

        state = rebuild_state()
        self.assertEqual(state["time_state"]["current_date"], "2026-01-01")
        self.assertEqual(state["profile"].occupation, "engineer")

        with open(es.EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            self.assertEqual(len([l for l in f if l.strip()]), 2)

    def test_apply_event_time_tick(self):
        state = get_initial_state()
        new_state = apply_event(
            state, {"type": "time_tick", "date": "2026-01-02", "previous_date": "2026-01-01"}
        )
        self.assertEqual(new_state["time_state"]["current_date"], "2026-01-02")
        self.assertEqual(new_state["time_state"]["previous_date"], "2026-01-01")

    def test_goal_and_task_lifecycle(self):
        state = get_initial_state()
        state = apply_event(
            state,
            {
                "type": "goal_created",
                "payload": {
                    "goal": {
                        "id": "goal_1",
                        "title": "Test Goal",
                        "description": "desc",
                        "source": "user_input",
                        "status": "active",
                    }
                },
            },
        )
        self.assertEqual(len(state["goals"]), 1)
        self.assertEqual(state["goals"][0].status, GoalStatus.ACTIVE)

        state = apply_event(
            state,
            {
                "type": "task_created",
                "payload": {
                    "task": {
                        "id": "task_1",
                        "goal_id": "goal_1",
                        "description": "Do work",
                        "scheduled_date": "2026-01-03",
                        "status": "pending",
                    }
                },
            },
        )
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(state["tasks"][0].status, TaskStatus.PENDING)

        state = apply_event(
            state,
            {
                "type": "task_updated",
                "payload": {"id": "task_1", "updates": {"status": "completed"}},
            },
        )
        self.assertEqual(state["tasks"][0].status, TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
