import json
import shutil
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import core.event_sourcing as event_sourcing
import core.goal_inference as goal_inference
import core.objective_engine.registry as registry_module
import core.retrospective as retrospective
import core.snapshot_manager as snapshot_manager
import core.strategic_engine.vision_inference as vision_inference
import tools.migrate_goals_to_registry as migrate_tool
import web.backend.routers.api as api_router
import web.backend.routers.tasks as tasks_router
from core.goal_inference import InferredGoal
from core.goal_service import GoalService
from core.objective_engine.models import GoalLayer, GoalSource, GoalState, ObjectiveNode
from core.objective_engine.registry import GoalRegistry
from core.strategic_engine.vision_inference import InferredVision
from web.backend.app import create_app


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    event_log = runtime_dir / "event_log.jsonl"
    state_snapshot = runtime_dir / "character_state.json"
    registry_path = runtime_dir / "goal_registry.json"
    snapshot_dir = runtime_dir / "snapshots"

    # Event and snapshot paths.
    monkeypatch.setattr(event_sourcing, "EVENT_LOG_PATH", event_log)
    monkeypatch.setattr(event_sourcing, "STATE_SNAPSHOT_PATH", state_snapshot)
    monkeypatch.setattr(snapshot_manager, "EVENT_LOG_PATH", event_log)
    monkeypatch.setattr(snapshot_manager, "STATE_SNAPSHOT_PATH", state_snapshot)
    monkeypatch.setattr(snapshot_manager, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(snapshot_manager, "should_create_snapshot", lambda interval=50: False)

    # Registry path.
    monkeypatch.setattr(registry_module, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(migrate_tool, "REGISTRY_PATH", registry_path)

    # Router/module-level imported constants.
    monkeypatch.setattr(api_router, "EVENT_LOG_PATH", event_log)
    monkeypatch.setattr(retrospective, "EVENT_LOG_PATH", event_log)

    return SimpleNamespace(
        runtime_dir=runtime_dir,
        event_log=event_log,
        state_snapshot=state_snapshot,
        registry_path=registry_path,
        snapshot_dir=snapshot_dir,
    )


@pytest.fixture
def client(isolated_runtime):
    return TestClient(create_app())


def _task_payload(task_id: str, goal_id: str, scheduled_time: str) -> dict:
    return {
        "id": task_id,
        "goal_id": goal_id,
        "description": f"task-{task_id}",
        "scheduled_date": date.today().isoformat(),
        "scheduled_time": scheduled_time,
        "estimated_minutes": 30,
        "status": "pending",
    }


def test_onboarding_generate_confirm_decompose_home_flow(client, monkeypatch):
    # Remove LLM dependency for this flow test.
    monkeypatch.setattr(
        GoalService,
        "generate_candidates",
        lambda self, n=3: [
            {
                "id": "vision_seed_1",
                "title": "Build Long-Term Vision",
                "description": "A deterministic test candidate",
                "layer": "goal",
                "source": "ai_generated",
                "_score": 0.91,
            }
        ],
    )
    monkeypatch.setattr(
        GoalService,
        "get_decomposition_questions",
        lambda self, goal_id: [
            {"id": "q1", "question": "Weekly bandwidth?", "options": ["5h", "10h"]}
        ],
    )
    monkeypatch.setattr(
        GoalService,
        "get_decomposition_options",
        lambda self, goal_id, context=None, n=3: {
            "action": "choose_option",
            "candidates": [
                {
                    "title": "Milestone A",
                    "description": "Deterministic decompose option",
                    "probability": 88,
                }
            ],
            "layer": "objective",
        },
    )

    assert client.get("/api/v1/onboarding/status").status_code == 200
    assert client.post("/api/v1/onboarding/answer", json={"answer": "Engineer"}).status_code == 200
    second_answer = client.post("/api/v1/onboarding/answer", json={"answer": "AI Systems"})
    assert second_answer.status_code == 200
    last_answer = client.post("/api/v1/onboarding/answer", json={"answer": "2h"})
    assert last_answer.status_code == 200
    assert last_answer.json()["completed"] is True

    generated = client.post("/api/v1/goals/generate", json={"n": 3})
    assert generated.status_code == 200
    candidates = generated.json()["candidates"]
    assert len(candidates) == 1

    confirmed = client.post("/api/v1/goals/confirm", json={"goal": candidates[0]})
    assert confirmed.status_code == 200
    goal_id = confirmed.json()["goal_id"]

    questions = client.get(f"/api/v1/goals/{goal_id}/questions")
    assert questions.status_code == 200
    assert questions.json()["questions"]

    options = client.post(
        f"/api/v1/goals/{goal_id}/decompose",
        json={"context": {"Weekly bandwidth?": "5h"}},
    )
    assert options.status_code == 200
    assert options.json()["candidates"]

    decompose = client.post(
        f"/api/v1/goals/{goal_id}/decompose",
        json={"selected_option": options.json()["candidates"][0]},
    )
    assert decompose.status_code == 200
    assert decompose.json()["success"] is True

    # Home page data dependencies.
    for path in [
        "/api/v1/state",
        "/api/v1/goals",
        "/api/v1/goals/tree",
        "/api/v1/tasks/list",
        "/api/v1/tasks/current",
        "/api/v1/retrospective",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path


def test_state_and_goal_route_views_are_consistent(client):
    service = GoalService()
    vision = service.create_node(
        title="Vision Root",
        layer=GoalLayer.VISION,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )
    objective = service.create_node(
        title="Objective Child",
        layer=GoalLayer.OBJECTIVE,
        state=GoalState.ACTIVE,
        source=GoalSource.TOP_DOWN.value,
        parent_id=vision.id,
    )
    goal = service.create_node(
        title="Goal Leaf",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.TOP_DOWN.value,
        parent_id=objective.id,
    )

    state_payload = client.get("/api/v1/state").json()
    canonical_payload = client.get("/api/v1/goals").json()
    tree_payload = client.get("/api/v1/goals/tree").json()["tree"]

    state_ids = {
        *(x["id"] for x in state_payload["visions"]),
        *(x["id"] for x in state_payload["objectives"]),
        *(x["id"] for x in state_payload["goals"]),
    }
    canonical_ids = {x["id"] for x in canonical_payload["goals"]}

    expected_ids = {vision.id, objective.id, goal.id}
    assert state_ids == expected_ids
    assert canonical_ids == expected_ids

    assert tree_payload
    assert tree_payload[0]["id"] == vision.id
    assert tree_payload[0]["children"][0]["id"] == objective.id
    assert tree_payload[0]["children"][0]["children"][0]["id"] == goal.id


def test_steward_cycle_does_not_create_duplicate_or_invisible_goals(client, monkeypatch):
    # Make state non-cold-start so Steward enters goal inference path.
    event_sourcing.append_event(
        {"type": "profile_updated", "payload": {"field": "occupation", "value": "Engineer"}}
    )
    event_sourcing.append_event(
        {
            "type": "time_tick",
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "previous_date": "",
        }
    )

    monkeypatch.setattr(
        vision_inference,
        "infer_vision",
        lambda *args, **kwargs: InferredVision(
            title="System Vision",
            description="Deterministic vision",
            target_outcome="Outcome",
            confidence=0.9,
            reasoning_chain=["r1"],
            information_edge=["i1"],
            source_signals={},
            bhb_alignment="aligned",
        ),
    )
    monkeypatch.setattr(
        goal_inference,
        "infer_goals_from_state",
        lambda state: [
            InferredGoal(
                title="System Goal",
                description="Deterministic goal",
                reasoning="r",
                confidence=0.8,
            )
        ],
    )

    first_cycle = client.post("/api/v1/sys/cycle")
    assert first_cycle.status_code == 200
    first_ids = {n.id for n in GoalService().list_nodes()}
    assert first_ids

    second_cycle = client.post("/api/v1/sys/cycle")
    assert second_cycle.status_code == 200
    second_ids = {n.id for n in GoalService().list_nodes()}

    # No duplicate goals added by repeated cycle.
    assert second_ids == first_ids

    # No invisible goals: every registry node is visible in /state response.
    state_payload = client.get("/api/v1/state").json()
    visible_ids = {
        *(x["id"] for x in state_payload["visions"]),
        *(x["id"] for x in state_payload["objectives"]),
        *(x["id"] for x in state_payload["goals"]),
    }
    assert second_ids == visible_ids


def test_task_complete_and_skip_work_with_canonical_goal_ids(client):
    service = GoalService()
    goal = service.create_node(
        title="Canonical Goal",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )

    event_sourcing.append_event(
        {"type": "task_created", "payload": {"task": _task_payload("task_1", goal.id, "09:00")}}
    )
    event_sourcing.append_event(
        {"type": "task_created", "payload": {"task": _task_payload("task_2", goal.id, "10:00")}}
    )

    current = client.get("/api/v1/tasks/current")
    assert current.status_code == 200
    assert current.json()["task"]["id"] == "task_1"
    assert current.json()["task"]["goal_id"] == goal.id
    assert current.json()["task"]["goal_title"] == goal.title

    complete = client.post("/api/v1/tasks/task_1/complete")
    assert complete.status_code == 200
    assert complete.json()["task"]["id"] == "task_2"

    skip = client.post(
        "/api/v1/tasks/task_2/skip",
        json={"reason": "postponed", "context": "resource_blocked"},
    )
    assert skip.status_code == 200
    assert skip.json()["recovery_task_id"] == "task_2_recovery"
    assert skip.json()["task"]["id"] == "task_2_recovery"

    listed = client.get("/api/v1/tasks/list")
    assert listed.status_code == 200
    completed_tasks = listed.json()["completed"]
    pending_tasks = listed.json()["pending"]
    assert any(t["id"] == "task_1" and t["goal_id"] == goal.id for t in completed_tasks)
    assert any(t["id"] == "task_1" and t["goal_title"] == goal.title for t in completed_tasks)
    assert any(t["id"] == "task_2_recovery" and t["goal_id"] == goal.id for t in pending_tasks)


def test_task_skip_rejects_invalid_context(client):
    service = GoalService()
    goal = service.create_node(
        title="Context Goal",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )
    event_sourcing.append_event(
        {"type": "task_created", "payload": {"task": _task_payload("task_ctx", goal.id, "09:00")}}
    )

    response = client.post(
        "/api/v1/tasks/task_ctx/skip",
        json={"reason": "later", "context": "invalid_ctx"},
    )
    assert response.status_code == 400


def test_task_skip_creates_recovery_task_with_same_goal_id(client, isolated_runtime):
    service = GoalService()
    goal = service.create_node(
        title="Recovery Goal",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )
    event_sourcing.append_event(
        {
            "type": "task_created",
            "payload": {"task": _task_payload("task_recover", goal.id, "09:00")},
        }
    )

    response = client.post(
        "/api/v1/tasks/task_recover/skip",
        json={"reason": "too big", "context": "task_too_big"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("recovery_task_id") == "task_recover_recovery"

    listed = client.get("/api/v1/tasks/list")
    assert listed.status_code == 200
    pending_tasks = listed.json()["pending"]
    recovery = next(t for t in pending_tasks if t["id"] == "task_recover_recovery")
    assert recovery["goal_id"] == goal.id
    assert "最小下一步" in recovery["description"]

    lines = isolated_runtime.event_log.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    skip_update = next(
        e for e in events
        if e.get("type") == "task_updated"
        and (e.get("payload") or {}).get("id") == "task_recover"
    )
    assert skip_update["payload"]["updates"]["skip_context"] == "task_too_big"
    recovery_created = next(
        e for e in events
        if e.get("type") == "task_created"
        and ((e.get("payload") or {}).get("task") or {}).get("id") == "task_recover_recovery"
    )
    assert recovery_created["payload"]["task"]["goal_id"] == goal.id
    recovery_suggested = next(
        e for e in events if e.get("type") == "task_recovery_suggested"
    )
    assert recovery_suggested["payload"]["split_candidates"]
    split_event = next(
        e for e in events if e.get("type") == "task_split_candidates_suggested"
    )
    assert len(split_event["payload"]["candidates"]) == 3


def test_tasks_current_reschedules_overdue_pending_task(client, isolated_runtime):
    service = GoalService()
    goal = service.create_node(
        title="Overdue Goal",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )
    overdue_payload = _task_payload("task_overdue", goal.id, "09:00")
    overdue_payload["scheduled_date"] = (date.today() - timedelta(days=1)).isoformat()
    event_sourcing.append_event({"type": "task_created", "payload": {"task": overdue_payload}})

    response = client.get("/api/v1/tasks/current")
    assert response.status_code == 200
    task = response.json()["task"]
    assert task["id"] == "task_overdue"
    assert task["scheduled_date"] == date.today().isoformat()

    events = [
        json.loads(line)
        for line in isolated_runtime.event_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reschedule_event = next(
        e
        for e in events
        if e.get("type") == "task_updated"
        and (e.get("payload") or {}).get("id") == "task_overdue"
        and ((e.get("payload") or {}).get("meta") or {}).get("reason") == "overdue_reschedule"
    )
    assert (
        (reschedule_event.get("payload") or {})
        .get("updates", {})
        .get("scheduled_date")
        == date.today().isoformat()
    )


def test_tasks_current_uses_low_pressure_recovery_priority_in_trust_repair(
    client,
    isolated_runtime,
    monkeypatch,
):
    monkeypatch.setattr(
        tasks_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "intervention_policy": {
                "mode": "trust_repair",
                "trust_repair": {
                    "active": True,
                    "repair_min_step": "Take one 10-minute minimal step now.",
                },
            }
        },
    )

    service = GoalService()
    goal = service.create_node(
        title="Trust Repair Goal",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    normal_task = _task_payload("task_regular", goal.id, "09:00")
    normal_task["scheduled_date"] = yesterday
    recovery_task = _task_payload("task_regular_recovery", goal.id, "14:00")
    recovery_task["scheduled_date"] = yesterday
    event_sourcing.append_event({"type": "task_created", "payload": {"task": normal_task}})
    event_sourcing.append_event({"type": "task_created", "payload": {"task": recovery_task}})

    response = client.get("/api/v1/tasks/current")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task"]["id"] == "task_regular_recovery"
    assert payload["dispatch_policy"]["mode"] == "trust_repair"
    assert payload["dispatch_policy"]["low_pressure"] is True
    assert payload["dispatch_policy"]["prioritize_recovery"] is True
    assert payload["dispatch_policy"]["repair_min_step"] == "Take one 10-minute minimal step now."

    events = [
        json.loads(line)
        for line in isolated_runtime.event_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    low_pressure_update = next(
        e
        for e in events
        if e.get("type") == "task_updated"
        and (e.get("payload") or {}).get("id") == "task_regular_recovery"
        and ((e.get("payload") or {}).get("meta") or {}).get("reason")
        == "overdue_reschedule_low_pressure"
    )
    assert low_pressure_update["payload"]["updates"]["scheduled_time"] == "Anytime"
    assert (
        (low_pressure_update.get("payload") or {})
        .get("meta", {})
        .get("low_pressure")
        is True
    )
    assert not any(
        e.get("type") == "task_updated"
        and (e.get("payload") or {}).get("id") == "task_regular"
        and ((e.get("payload") or {}).get("meta") or {}).get("reason")
        == "overdue_reschedule_low_pressure"
        for e in events
    )


def test_recovery_batch_preview_and_apply(client, isolated_runtime):
    service = GoalService()
    goal = service.create_node(
        title="Batch Recovery Goal",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT.value,
    )
    past_day = (date.today() - timedelta(days=1)).isoformat()
    event_sourcing.append_event(
        {
            "type": "task_created",
            "payload": {
                "task": {
                    **_task_payload("task_a_recovery", goal.id, "09:00"),
                    "scheduled_date": past_day,
                    "status": "pending",
                }
            },
        }
    )
    event_sourcing.append_event(
        {
            "type": "task_created",
            "payload": {
                "task": {
                    **_task_payload("task_b_recovery", goal.id, "Afternoon"),
                    "scheduled_date": past_day,
                    "status": "pending",
                }
            },
        }
    )
    event_sourcing.append_event(
        {
            "type": "task_created",
            "payload": {
                "task": {
                    **_task_payload("task_c", goal.id, "Anytime"),
                    "scheduled_date": date.today().isoformat(),
                    "status": "pending",
                }
            },
        }
    )

    preview = client.get("/api/v1/tasks/recovery/batch/preview")
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["count"] == 2
    assert {task["id"] for task in preview_payload["tasks"]} == {
        "task_a_recovery",
        "task_b_recovery",
    }

    apply_resp = client.post("/api/v1/tasks/recovery/batch/apply")
    assert apply_resp.status_code == 200
    apply_payload = apply_resp.json()
    assert apply_payload["recovery_batch"]["applied_count"] == 2
    assert set(apply_payload["recovery_batch"]["task_ids"]) == {
        "task_a_recovery",
        "task_b_recovery",
    }

    events = [
        json.loads(line)
        for line in isolated_runtime.event_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    batch_updates = [
        e
        for e in events
        if e.get("type") == "task_updated"
        and ((e.get("payload") or {}).get("meta") or {}).get("reason") == "recovery_batch_apply"
    ]
    assert len(batch_updates) == 2


def test_retrospective_and_state_expose_intervention_contract(client, monkeypatch):
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "period": {"days": days, "start_date": "2026-02-01", "end_date": "2026-02-07"},
            "generated_at": datetime.now().isoformat(),
            "rhythm": {"broken": False, "summary": "ok"},
            "alignment": {"deviated": False, "summary": "ok"},
            "friction": {"repeated_skip": False, "delay_signals": False, "summary": "ok"},
            "deviation_signals": [],
            "observations": ["ok"],
            "intervention_level": "ASK",
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": True,
            "suggestion_sources": [],
            "response_action": {
                "required": True,
                "pending": True,
                "allowed_actions": ["confirm", "snooze", "dismiss"],
                "latest": None,
                "endpoint": "/api/v1/retrospective/respond",
                "method": "POST",
                "fingerprint": "gcf_contract",
            },
            "confirmation_action": {
                "required": True,
                "confirmed": False,
                "confirmed_at": None,
                "endpoint": "/api/v1/retrospective/confirm",
                "method": "POST",
                "fingerprint": "gcf_contract",
            },
            "authority": {
                "escalation": {"stage": "gentle_nudge"},
                "safe_mode": {
                    "enabled": True,
                    "active": False,
                    "recommendation": {"should_enter": False, "should_exit": False},
                },
            },
        },
    )

    retro = client.get("/api/v1/retrospective")
    assert retro.status_code == 200
    payload = retro.json()
    assert payload["intervention_level"] == "ASK"
    assert payload["require_confirm"] is True
    assert payload["confirmation_action"]["endpoint"] == "/api/v1/retrospective/confirm"
    assert payload["response_action"]["endpoint"] == "/api/v1/retrospective/respond"

    state = client.get("/api/v1/state")
    assert state.status_code == 200
    state_payload = state.json()
    assert "guardian" in state_payload
    assert state_payload["guardian"]["pending_confirmation"] is True
    assert state_payload["guardian"]["confirmation_action"]["fingerprint"] == "gcf_contract"
    assert state_payload["guardian"]["response_action"]["fingerprint"] == "gcf_contract"


def test_migration_backup_supports_manual_rollback(isolated_runtime):
    registry = GoalRegistry(path=isolated_runtime.registry_path)
    registry.add_node(
        ObjectiveNode(
            id="existing_goal",
            title="Existing Goal",
            description="before migration",
            layer=GoalLayer.GOAL,
            state=GoalState.ACTIVE,
            source=GoalSource.USER_INPUT,
        )
    )
    original_registry_content = isolated_runtime.registry_path.read_text(encoding="utf-8")

    legacy_event = {
        "type": "goal_created",
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "goal": {
                "id": "legacy_goal_1",
                "title": "Legacy Goal",
                "description": "from event log",
                "source": "user_input",
                "status": "active",
                "horizon": "goal",
                "depends_on": [],
                "resource_description": "",
                "target_level": "",
                "tags": [],
            }
        },
    }
    isolated_runtime.event_log.write_text(
        json.dumps(legacy_event, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    code = migrate_tool.migrate(apply=True, update_existing=False)
    assert code == 0

    migrated_content = isolated_runtime.registry_path.read_text(encoding="utf-8")
    assert migrated_content != original_registry_content

    backups = sorted(isolated_runtime.registry_path.parent.glob("goal_registry.backup_*.json"))
    assert backups

    shutil.copy2(backups[-1], isolated_runtime.registry_path)
    rolled_back_content = isolated_runtime.registry_path.read_text(encoding="utf-8")
    assert rolled_back_content == original_registry_content
