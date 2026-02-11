import asyncio
import json
from types import SimpleNamespace

import core.event_sourcing as event_sourcing
import core.snapshot_manager as snapshot_manager
import web.backend.routers.api as api_router
from core.goal_service import GoalService
from core.objective_engine.models import GoalLayer, GoalSource, GoalState, ObjectiveNode
from core.objective_engine.registry import GoalRegistry
from core.steward import Steward


def test_layer_mapping():
    assert GoalService.layer_from_string("vision") == GoalLayer.VISION
    assert GoalService.layer_from_string("objective") == GoalLayer.OBJECTIVE
    assert GoalService.layer_from_string("goal") == GoalLayer.GOAL
    assert GoalService.decomposition_horizon_from_layer(GoalLayer.VISION) == "vision"
    assert GoalService.decomposition_horizon_from_layer(GoalLayer.OBJECTIVE) == "milestone"
    assert GoalService.decomposition_horizon_from_layer(GoalLayer.GOAL) == "goal"


def test_status_mapping():
    assert (
        GoalService.state_from_string("vision_pending_confirmation")
        == GoalState.VISION_PENDING_CONFIRMATION
    )
    assert GoalService.state_from_string("active") == GoalState.ACTIVE
    assert GoalService.state_from_string("completed") == GoalState.COMPLETED
    assert GoalService.state_from_string("archived") == GoalState.ARCHIVED
    assert GoalService.state_from_string("pending_confirm") == GoalState.VISION_PENDING_CONFIRMATION


def test_node_to_dict_is_canonical(tmp_path):
    registry = GoalRegistry(path=tmp_path / "goal_registry.json")
    service = GoalService(registry=registry)
    node = ObjectiveNode(
        id="g_1",
        title="Test Goal",
        description="desc",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
        source=GoalSource.USER_INPUT,
    )
    payload = service.node_to_dict(node)

    assert payload["id"] == "g_1"
    assert payload["layer"] == "goal"
    assert payload["state"] == "active"
    assert "horizon" not in payload
    assert "status" not in payload


def test_normalize_title():
    assert GoalService.normalize_title("Option 1: Build MVP") == "Build MVP"
    assert GoalService.normalize_title("选项A - 每天写作") == "每天写作"
    assert GoalService.normalize_title("Plain Title") == "Plain Title"


def test_goal_service_applies_anchor_alignment_when_creating_node(tmp_path):
    registry = GoalRegistry(path=tmp_path / "goal_registry.json")
    service = GoalService(registry=registry)

    class DummyAnchor:
        version = "v9"
        long_horizon_commitments = ("Write deeply", "Ship meaningful products")
        anti_values = ("doomscroll",)

    class DummyAnchorManager:
        @staticmethod
        def get_current():
            return DummyAnchor()

    service.anchor_manager = DummyAnchorManager()

    node = service.create_node(
        title="Write deeply every morning",
        description="Avoid doomscroll and ship meaningful products",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
    )

    assert node.anchor_version == "v9"
    assert node.alignment_level in {"high", "medium", "low"}
    assert node.alignment_score is not None
    assert "Write deeply" in node.matched_commitments
    assert "doomscroll" in node.matched_anti_values


def test_recompute_active_alignment_updates_nodes(tmp_path, monkeypatch):
    monkeypatch.setattr("core.goal_service.append_event", lambda event: None)
    registry = GoalRegistry(path=tmp_path / "goal_registry.json")
    service = GoalService(registry=registry)

    class AnchorV1:
        version = "v1"
        long_horizon_commitments = ("Write deeply",)
        anti_values = ("doomscroll",)

    class AnchorV2:
        version = "v2"
        long_horizon_commitments = ("Ship weekly",)
        anti_values = ("doomscroll",)

    class DummyAnchorManager:
        def __init__(self):
            self.anchor = AnchorV1()

        def get_current(self):
            return self.anchor

    dummy_manager = DummyAnchorManager()
    service.anchor_manager = dummy_manager

    node = service.create_node(
        title="Write deeply every morning",
        description="Avoid doomscroll",
        layer=GoalLayer.GOAL,
        state=GoalState.ACTIVE,
    )
    assert node.anchor_version == "v1"

    dummy_manager.anchor = AnchorV2()
    result = service.recompute_active_alignment(detail_limit=10)
    refreshed = service.require_node(node.id)

    assert result["total_processed"] >= 1
    assert result["affected_count"] >= 1
    assert refreshed.anchor_version == "v2"
    assert result["after"]["total_active"] == result["total_processed"]


def test_append_event_injects_canonical_metadata(tmp_path, monkeypatch):
    log_path = tmp_path / "event_log.jsonl"
    monkeypatch.setattr(event_sourcing, "EVENT_LOG_PATH", log_path)
    monkeypatch.setattr(snapshot_manager, "create_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(snapshot_manager, "should_create_snapshot", lambda *args, **kwargs: False)

    event_sourcing.append_event({"type": "unit_test_event", "payload": {"value": 1}})

    raw = log_path.read_text(encoding="utf-8").strip()
    saved = json.loads(raw)
    assert saved["type"] == "unit_test_event"
    assert saved["schema_version"] == event_sourcing.EVENT_SCHEMA_VERSION
    assert saved["event_id"].startswith("evt_")
    assert "timestamp" in saved


def test_state_endpoint_includes_stable_audit_shape(monkeypatch):
    class DummyGoalService:
        @staticmethod
        def node_to_dict(node):  # pragma: no cover - defensive
            return {"id": node.id}

        @staticmethod
        def summarize_alignment(nodes):  # pragma: no cover - defensive
            return {
                "total_active": len(nodes),
                "avg_score": 66.0,
                "distribution": {"high": 1, "medium": 0, "low": 0, "unknown": 0},
            }

    class DummySteward:
        def __init__(self):
            self.state = {
                "identity": {"occupation": "dev"},
                "rhythm": {},
                "ongoing": {"active_tasks": []},
            }
            self.registry = SimpleNamespace(visions=[], objectives=[], goals=[])

        @staticmethod
        def get_current_phase():
            return "deep_work"

    monkeypatch.setattr(api_router, "get_steward", lambda: DummySteward())
    monkeypatch.setattr(api_router, "get_goal_service", lambda: DummyGoalService())
    monkeypatch.setattr(api_router, "_has_review_due_this_week", lambda: False)
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "intervention_level": "ASK",
            "require_confirm": True,
            "l2_protection": {
                "ratio": 0.6,
                "level": "medium",
                "summary": "L2 保护一般",
                "trend": [],
            },
            "confirmation_action": {
                "required": True,
                "confirmed": False,
                "confirmed_at": None,
                "endpoint": "/api/v1/retrospective/confirm",
                "method": "POST",
                "fingerprint": "gcf_dummy",
            },
        },
    )

    payload = asyncio.run(api_router.get_state())
    assert "audit" in payload
    assert payload["audit"]["strategy"] == "state_projection"
    assert isinstance(payload["audit"]["used_state_fields"], list)
    assert set(payload["audit"]["decision_reason"]) == {"trigger", "constraint", "risk"}
    assert payload["guardian"]["intervention_level"] == "ASK"
    assert payload["guardian"]["pending_confirmation"] is True
    assert payload["guardian"]["confirmation_action"]["endpoint"] == "/api/v1/retrospective/confirm"
    assert payload["guardian"]["metrics"]["l2_protection_rate"] == 0.6
    assert "alignment" in payload
    assert "goal_summary" in payload["alignment"]
    assert payload["meta"]["event_schema_version"] == event_sourcing.EVENT_SCHEMA_VERSION


def test_sys_cycle_normalizes_audit_shape(monkeypatch):
    class DummySteward:
        @staticmethod
        def run_planning_cycle():
            return {"actions": [], "executed_auto_tasks": [], "audit": {"strategy": "custom"}}

    monkeypatch.setattr(api_router, "get_steward", lambda: DummySteward())

    payload = asyncio.run(api_router.trigger_cycle())
    assert payload["status"] == "cycled"
    assert payload["audit"]["strategy"] == "custom"
    assert isinstance(payload["audit"]["used_state_fields"], list)
    assert set(payload["audit"]["decision_reason"]) == {"trigger", "constraint", "risk"}


def test_sys_cycle_preserves_anchor_audit_extension(monkeypatch):
    class DummySteward:
        @staticmethod
        def run_planning_cycle():
            return {
                "actions": [],
                "executed_auto_tasks": [],
                "audit": {
                    "strategy": "custom",
                    "anchor": {
                        "enabled": True,
                        "active_version": "v1",
                        "blocked_actions": 1,
                        "block_reasons": [{"action_id": "a1", "anti_value": "doomscroll"}],
                    },
                },
            }

    monkeypatch.setattr(api_router, "get_steward", lambda: DummySteward())
    payload = asyncio.run(api_router.trigger_cycle())

    assert "anchor" in payload["audit"]
    assert payload["audit"]["anchor"]["enabled"] is True
    assert payload["audit"]["anchor"]["blocked_actions"] == 1


def test_confirm_retrospective_intervention_appends_confirmation_event(monkeypatch):
    emitted = []
    snapshots = [
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "require_confirm": True,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "confirmation_action": {
                "required": True,
                "confirmed": False,
                "fingerprint": "gcf_test_1",
            },
        },
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "confirmation_action": {
                "required": True,
                "confirmed": True,
                "fingerprint": "gcf_test_1",
            },
        },
    ]

    def fake_build(days=7):
        return snapshots.pop(0)

    monkeypatch.setattr(api_router, "build_guardian_retrospective_response", fake_build)
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    req = api_router.RetrospectiveConfirmRequest(days=7, fingerprint="gcf_test_1")
    payload = asyncio.run(api_router.confirm_retrospective_intervention(req))

    assert payload["status"] == "confirmed"
    assert emitted
    assert emitted[0]["type"] == "guardian_intervention_confirmed"
    assert emitted[0]["payload"]["fingerprint"] == "gcf_test_1"
    assert emitted[0]["payload"]["signals"] == ["repeated_skip"]


def test_confirm_retrospective_intervention_rejects_stale_fingerprint(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "require_confirm": True,
            "suggestion_sources": [],
            "confirmation_action": {
                "required": True,
                "confirmed": False,
                "fingerprint": "gcf_latest",
            },
        },
    )

    req = api_router.RetrospectiveConfirmRequest(days=7, fingerprint="gcf_old")
    try:
        asyncio.run(api_router.confirm_retrospective_intervention(req))
    except Exception as exc:  # FastAPI HTTPException
        assert getattr(exc, "status_code", None) == 409
    else:  # pragma: no cover - defensive
        assert False, "Expected 409 for stale fingerprint"


def test_steward_anchor_filter_records_reasons(tmp_path):
    registry = GoalRegistry(path=tmp_path / "goal_registry.json")
    steward = Steward(state={}, registry=registry)

    class DummyAnchor:
        version = "v_anchor"
        anti_values = ("doomscroll",)

    class DummyAnchorManager:
        @staticmethod
        def get_current():
            return DummyAnchor()

    steward._anchor_manager = DummyAnchorManager()
    steward._anchor_blocked_actions = []
    steward._active_anchor_version = None

    filtered = steward._filter_actions_by_anchor(
        [
            {"id": "a1", "description": "doomscroll for 30 minutes"},
            {"id": "a2", "description": "write weekly report"},
        ]
    )

    assert len(filtered) == 1
    assert filtered[0]["id"] == "a2"
    assert steward._active_anchor_version == "v_anchor"
    assert steward._anchor_blocked_actions[0]["action_id"] == "a1"
    assert steward._anchor_blocked_actions[0]["anti_value"] == "doomscroll"


def test_activate_anchor_triggers_recompute_and_effect_event(monkeypatch, tmp_path):
    blueprint = tmp_path / "better_human_blueprint.md"
    blueprint.write_text("blueprint", encoding="utf-8")
    emitted = []

    class DummyAnchor:
        def __init__(self, version, confirmed_by_user):
            self.version = version
            self.created_at = "2026-02-11T00:00:00"
            self.confirmed_by_user = confirmed_by_user
            self.non_negotiables = ()
            self.long_horizon_commitments = ("ship weekly",)
            self.anti_values = ("doomscroll",)
            self.instinct_adversaries = ()
            self.source_hash = "hash"

    class DummyAnchorManager:
        def __init__(self):
            self.current = DummyAnchor("v1", True)

        def get_current(self):
            return self.current

        @staticmethod
        def generate_draft(path):
            assert path.endswith("better_human_blueprint.md")
            return DummyAnchor("v2", False)

        @staticmethod
        def diff(old, new):
            return SimpleNamespace(
                status="changed",
                version_change=f"{old.version} -> {new.version}",
                added_non_negotiables=set(),
                removed_non_negotiables=set(),
                added_commitments={"ship weekly"},
                removed_commitments=set(),
                added_anti_values=set(),
                removed_anti_values=set(),
                added_adversaries=set(),
                removed_adversaries=set(),
            )

        def activate(self, anchor):
            self.current = DummyAnchor(anchor.version, True)
            return self.current

    class DummyGoalService:
        @staticmethod
        def recompute_active_alignment(detail_limit=100):
            return {
                "total_processed": 3,
                "affected_count": 2,
                "avg_score_delta": 8.0,
                "before": {
                    "total_active": 3,
                    "avg_score": 55.0,
                    "distribution": {"high": 0, "medium": 2, "low": 1, "unknown": 0},
                },
                "after": {
                    "total_active": 3,
                    "avg_score": 63.0,
                    "distribution": {"high": 1, "medium": 2, "low": 0, "unknown": 0},
                },
                "impacted_goals": [{"goal_id": "g_1"}],
            }

    monkeypatch.setattr(api_router, "BLUEPRINT_PATH", blueprint)
    monkeypatch.setattr(api_router, "AnchorManager", DummyAnchorManager)
    monkeypatch.setattr(api_router, "get_goal_service", lambda: DummyGoalService())
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    payload = asyncio.run(
        api_router.activate_anchor(api_router.AnchorActivateRequest(force=False))
    )

    assert payload["status"] == "activated"
    assert payload["effect"]["available"] is True
    assert payload["effect"]["affected_count"] == 2
    assert any(event["type"] == "anchor_activated" for event in emitted)
    assert any(event["type"] == "goal_alignment_recomputed" for event in emitted)


def test_anchor_effect_returns_latest_recompute_event(monkeypatch, tmp_path):
    event_log = tmp_path / "event_log.jsonl"
    event_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "goal_alignment_recomputed",
                        "timestamp": "2026-02-11T10:00:00",
                        "payload": {
                            "anchor_version": "v2",
                            "total_processed": 3,
                            "affected_count": 2,
                            "avg_score_delta": 8.0,
                            "before": {"total_active": 3, "avg_score": 55.0},
                            "after": {"total_active": 3, "avg_score": 63.0},
                            "impacted_goals": [{"goal_id": "g_1"}],
                        },
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(api_router, "EVENT_LOG_PATH", event_log)
    payload = asyncio.run(api_router.get_anchor_effect())

    assert payload["available"] is True
    assert payload["anchor_version"] == "v2"
    assert payload["affected_count"] == 2
    assert payload["generated_at"] == "2026-02-11T10:00:00"
