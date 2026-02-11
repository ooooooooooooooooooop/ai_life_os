import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
import yaml

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
                "thresholds": {"high": 0.75, "medium": 0.5},
            },
            "humanization_metrics": {
                "recovery_adoption_rate": {"rate": 0.5},
                "friction_load": {"score": 0.67, "level": "high"},
                "support_vs_override": {"support_ratio": 0.4, "mode": "balanced"},
            },
            "intervention_policy": {
                "mode": "balanced_intervention",
                "reason": "Medium-severity deviation is active, so Guardian uses balanced cadence.",
                "friction_budget": {"suppressed": False},
            },
            "north_star_metrics": {
                "window_days": 7,
                "mundane_automation_coverage": {"rate": 0.55, "met_target": True},
                "l2_bloom_hours": {"hours": 3.0, "met_target": True},
                "human_trust_index": {"score": 0.7, "met_target": True},
                "alignment_delta_weekly": {"delta": 4.0, "met_target": True},
                "targets_met": {"met_count": 4, "total": 4},
            },
            "explainability": {
                "why_this_suggestion": "Suggestion is triggered by: repeated_skip 2/2.",
                "what_happens_next": (
                    "ASK mode is active: confirm this suggestion or respond with context."
                ),
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
    assert "retrospective.humanization_metrics" in payload["audit"]["used_state_fields"]
    assert "retrospective.north_star_metrics" in payload["audit"]["used_state_fields"]
    assert "retrospective.intervention_policy" in payload["audit"]["used_state_fields"]
    assert "retrospective.blueprint_narrative" in payload["audit"]["used_state_fields"]
    assert set(payload["audit"]["decision_reason"]) == {"trigger", "constraint", "risk"}
    assert payload["guardian"]["intervention_level"] == "ASK"
    assert payload["guardian"]["pending_confirmation"] is True
    assert payload["guardian"]["confirmation_action"]["endpoint"] == "/api/v1/retrospective/confirm"
    assert "guardian_role" in payload["guardian"]
    assert payload["guardian"]["policy"]["mode"] == "balanced_intervention"
    assert "blueprint_narrative" in payload["guardian"]
    assert payload["guardian"]["explainability"]["why_this_suggestion"].startswith(
        "Suggestion is triggered by:"
    )
    assert payload["guardian"]["metrics"]["l2_protection_rate"] == 0.6
    assert payload["guardian"]["metrics"]["l2_protection_thresholds"]["high"] == 0.75
    assert payload["guardian"]["metrics"]["recovery_adoption_rate"] == 0.5
    assert payload["guardian"]["metrics"]["friction_load"]["score"] == 0.67
    assert payload["guardian"]["metrics"]["support_vs_override"]["mode"] == "balanced"
    assert payload["guardian"]["metrics"]["north_star"]["window_days"] == 7
    assert payload["guardian"]["metrics"]["mundane_automation_coverage"] == 0.55
    assert payload["guardian"]["metrics"]["human_trust_index"] == 0.7
    assert payload["guardian"]["metrics"]["alignment_delta_weekly"] == 4.0
    assert "alignment" in payload
    assert "goal_summary" in payload["alignment"]
    assert payload["meta"]["event_schema_version"] == event_sourcing.EVENT_SCHEMA_VERSION


def test_get_guardian_config_defaults_when_file_missing(monkeypatch, tmp_path):
    missing_path = tmp_path / "blueprint.yaml"
    monkeypatch.setattr(api_router, "BLUEPRINT_CONFIG_PATH", missing_path)

    payload = asyncio.run(api_router.get_guardian_config())
    config = payload["config"]

    assert config["intervention_level"] == "SOFT"
    assert config["thresholds"]["deviation_signals"]["repeated_skip"] == 2
    assert config["thresholds"]["l2_protection"]["high"] == 0.75
    assert config["authority"]["escalation"]["window_days"] == 7
    assert config["authority"]["safe_mode"]["enabled"] is True


def test_get_guardian_autotune_config_defaults_when_file_missing(monkeypatch, tmp_path):
    missing_path = tmp_path / "blueprint.yaml"
    monkeypatch.setattr(api_router, "BLUEPRINT_CONFIG_PATH", missing_path)

    payload = asyncio.run(api_router.get_guardian_autotune_config())
    config = payload["config"]

    assert config["enabled"] is False
    assert config["mode"] == "shadow"
    assert config["llm_enabled"] is True
    assert config["trigger"]["lookback_days"] == 7
    assert config["guardrails"]["max_int_step"] == 1


def test_update_guardian_autotune_config_persists_and_emits_event(monkeypatch, tmp_path):
    config_path = tmp_path / "blueprint.yaml"
    config_path.write_text("intervention_level: SOFT\n", encoding="utf-8")
    emitted = []

    monkeypatch.setattr(api_router, "BLUEPRINT_CONFIG_PATH", config_path)
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    req = api_router.GuardianAutoTuneConfigUpdateRequest(
        enabled=True,
        mode="shadow",
        llm_enabled=False,
        trigger=api_router.GuardianAutoTuneTriggerConfigRequest(
            lookback_days=9,
            min_event_count=12,
            cooldown_hours=36,
        ),
        guardrails=api_router.GuardianAutoTuneGuardrailsConfigRequest(
            max_int_step=1,
            max_float_step=0.05,
            min_confidence=0.6,
        ),
    )

    payload = asyncio.run(api_router.update_guardian_autotune_config(req))
    assert payload["status"] == "updated"
    assert payload["config"]["enabled"] is True
    assert payload["config"]["llm_enabled"] is False
    assert payload["config"]["trigger"]["cooldown_hours"] == 36
    assert emitted and emitted[0]["type"] == "guardian_autotune_config_updated"

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["guardian_autotune"]["enabled"] is True
    assert saved["guardian_autotune"]["trigger"]["min_event_count"] == 12


def test_update_guardian_config_persists_and_emits_event(monkeypatch, tmp_path):
    config_path = tmp_path / "blueprint.yaml"
    config_path.write_text("intervention_level: SOFT\n", encoding="utf-8")
    emitted = []

    monkeypatch.setattr(api_router, "BLUEPRINT_CONFIG_PATH", config_path)
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    req = api_router.GuardianConfigUpdateRequest(
        intervention_level="ASK",
        deviation_signals=api_router.GuardianDeviationThresholdsRequest(
            repeated_skip=4,
            l2_interruption=2,
            stagnation_days=5,
        ),
        l2_protection=api_router.GuardianL2ThresholdsRequest(high=0.8, medium=0.6),
        authority=api_router.GuardianAuthorityConfigRequest(
            escalation=api_router.GuardianEscalationConfigRequest(
                window_days=9,
                firm_reminder_resistance=3,
                periodic_check_resistance=5,
            ),
            safe_mode=api_router.GuardianSafeModeConfigRequest(
                enabled=True,
                resistance_threshold=6,
                min_response_events=4,
                max_confirmation_ratio=0.3,
                recovery_confirmations=2,
                cooldown_hours=36,
            ),
        ),
    )

    payload = asyncio.run(api_router.update_guardian_config(req))

    assert payload["status"] == "updated"
    assert payload["config"]["intervention_level"] == "ASK"
    assert payload["config"]["thresholds"]["deviation_signals"]["repeated_skip"] == 4
    assert payload["config"]["thresholds"]["l2_protection"]["high"] == 0.8
    assert payload["config"]["authority"]["escalation"]["window_days"] == 9
    assert emitted and emitted[0]["type"] == "guardian_config_updated"

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["intervention_level"] == "ASK"
    assert saved["guardian_thresholds"]["deviation_signals"]["stagnation_days"] == 5
    assert saved["guardian_authority"]["safe_mode"]["cooldown_hours"] == 36


def test_update_guardian_config_rejects_invalid_l2_thresholds():
    req = api_router.GuardianConfigUpdateRequest(
        intervention_level="SOFT",
        deviation_signals=api_router.GuardianDeviationThresholdsRequest(
            repeated_skip=2,
            l2_interruption=1,
            stagnation_days=3,
        ),
        l2_protection=api_router.GuardianL2ThresholdsRequest(high=0.5, medium=0.7),
    )

    try:
        asyncio.run(api_router.update_guardian_config(req))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        assert False, "Expected 400 when l2_protection.medium > l2_protection.high"


def test_update_guardian_config_preserves_authority_when_not_provided(monkeypatch, tmp_path):
    config_path = tmp_path / "blueprint.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "intervention_level": "SOFT",
                "guardian_authority": {
                    "escalation": {
                        "window_days": 11,
                        "firm_reminder_resistance": 2,
                        "periodic_check_resistance": 6,
                    },
                    "safe_mode": {
                        "enabled": True,
                        "resistance_threshold": 7,
                        "min_response_events": 4,
                        "max_confirmation_ratio": 0.25,
                        "recovery_confirmations": 2,
                        "cooldown_hours": 48,
                    },
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_router, "BLUEPRINT_CONFIG_PATH", config_path)
    monkeypatch.setattr(api_router, "append_event", lambda event: None)

    req = api_router.GuardianConfigUpdateRequest(
        intervention_level="SOFT",
        deviation_signals=api_router.GuardianDeviationThresholdsRequest(
            repeated_skip=3,
            l2_interruption=1,
            stagnation_days=4,
        ),
        l2_protection=api_router.GuardianL2ThresholdsRequest(high=0.8, medium=0.6),
    )
    payload = asyncio.run(api_router.update_guardian_config(req))

    assert payload["config"]["authority"]["escalation"]["window_days"] == 11
    assert payload["config"]["authority"]["safe_mode"]["resistance_threshold"] == 7


def test_sys_cycle_normalizes_audit_shape(monkeypatch):
    class DummySteward:
        @staticmethod
        def run_planning_cycle():
            return {"actions": [], "executed_auto_tasks": [], "audit": {"strategy": "custom"}}

    monkeypatch.setattr(api_router, "get_steward", lambda: DummySteward())
    monkeypatch.setattr(
        api_router,
        "_run_guardian_autotune_shadow",
        lambda trigger="cycle": {"status": "disabled", "mode": "shadow"},
    )

    payload = asyncio.run(api_router.trigger_cycle())
    assert payload["status"] == "cycled"
    assert payload["guardian_autotune"]["status"] == "disabled"
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
    monkeypatch.setattr(
        api_router,
        "_run_guardian_autotune_shadow",
        lambda trigger="cycle": {"status": "disabled", "mode": "shadow"},
    )
    payload = asyncio.run(api_router.trigger_cycle())

    assert "anchor" in payload["audit"]
    assert payload["audit"]["anchor"]["enabled"] is True
    assert payload["audit"]["anchor"]["blocked_actions"] == 1


def test_run_guardian_autotune_shadow_proposes_patch(monkeypatch):
    emitted = []
    monkeypatch.setattr(
        api_router,
        "_load_blueprint_yaml",
        lambda: {
            "intervention_level": "SOFT",
            "guardian_thresholds": {
                "deviation_signals": {
                    "repeated_skip": 2,
                    "l2_interruption": 1,
                    "stagnation_days": 3,
                },
                "l2_protection": {"high": 0.75, "medium": 0.50},
            },
            "guardian_autotune": {
                "enabled": True,
                "mode": "shadow",
                "llm_enabled": False,
                "trigger": {
                    "lookback_days": 7,
                    "min_event_count": 1,
                    "cooldown_hours": 24,
                },
                "guardrails": {
                    "max_int_step": 1,
                    "max_float_step": 0.05,
                    "min_confidence": 0.55,
                },
            },
        },
    )
    monkeypatch.setattr(
        api_router,
        "_load_events_for_days",
        lambda days: [{"type": "task_updated", "timestamp": "2026-02-11T10:00:00"}],
    )
    monkeypatch.setattr(api_router, "_load_latest_event", lambda event_type: None)
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "humanization_metrics": {
                "friction_load": {"score": 0.82, "level": "high"},
                "recovery_adoption_rate": {"rate": 0.25},
                "support_vs_override": {"support_ratio": 0.2},
            },
            "l2_protection": {"ratio": 0.3, "level": "low"},
            "deviation_signals": [],
        },
    )
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    payload = asyncio.run(
        api_router.run_guardian_autotune_shadow(
            api_router.GuardianAutoTuneRunRequest(trigger="manual")
        )
    )
    assert payload["status"] == "proposed"
    assert payload["mode"] == "shadow"
    assert "repeated_skip" in payload["proposal"]["patch"]
    assert emitted and emitted[0]["type"] == "guardian_autotune_shadow_proposed"


def test_run_guardian_autotune_shadow_respects_cooldown(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "_load_blueprint_yaml",
        lambda: {
            "guardian_autotune": {
                "enabled": True,
                "mode": "shadow",
                "llm_enabled": False,
                "trigger": {
                    "lookback_days": 7,
                    "min_event_count": 1,
                    "cooldown_hours": 24,
                },
                "guardrails": {
                    "max_int_step": 1,
                    "max_float_step": 0.05,
                    "min_confidence": 0.55,
                },
            }
        },
    )
    monkeypatch.setattr(
        api_router,
        "_load_latest_event",
        lambda event_type: {"type": event_type, "timestamp": datetime.now().isoformat()},
    )

    payload = asyncio.run(
        api_router.run_guardian_autotune_shadow(
            api_router.GuardianAutoTuneRunRequest(trigger="manual")
        )
    )
    assert payload["status"] == "skipped"
    assert payload["reason"] == "cooldown_active"


def test_confirm_retrospective_intervention_appends_confirmation_event(monkeypatch):
    emitted = []
    snapshots = [
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": True,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": True,
                "pending": True,
                "fingerprint": "gcf_test_1",
                "latest": None,
            },
            "confirmation_action": {
                "required": True,
                "confirmed": False,
                "fingerprint": "gcf_test_1",
            },
        },
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": True,
                "pending": False,
                "fingerprint": "gcf_test_1",
                "latest": {
                    "action": "confirm",
                    "fingerprint": "gcf_test_1",
                    "timestamp": "2026-02-11T12:00:00",
                },
            },
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

    req = api_router.RetrospectiveConfirmRequest(
        days=7,
        fingerprint="gcf_test_1",
        context="recovering",
    )
    payload = asyncio.run(api_router.confirm_retrospective_intervention(req))

    assert payload["status"] == "confirmed"
    assert emitted
    assert emitted[0]["type"] == "guardian_intervention_confirmed"
    assert emitted[0]["payload"]["fingerprint"] == "gcf_test_1"
    assert emitted[0]["payload"]["context"] == "recovering"
    assert emitted[0]["payload"]["signals"] == ["repeated_skip"]


def test_confirm_retrospective_intervention_rejects_stale_fingerprint(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": True,
            "suggestion_sources": [],
            "response_action": {
                "required": True,
                "pending": True,
                "fingerprint": "gcf_latest",
                "latest": None,
            },
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


def test_respond_retrospective_intervention_appends_response_event(monkeypatch):
    emitted = []
    snapshots = [
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_resp_1",
                "latest": None,
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_resp_1",
            },
            "authority": {"safe_mode": {"active": False, "recommendation": {}}},
        },
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_resp_1",
                "latest": {
                    "action": "dismiss",
                    "fingerprint": "gcf_resp_1",
                    "timestamp": "2026-02-11T12:10:00",
                },
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_resp_1",
            },
            "authority": {"safe_mode": {"active": False, "recommendation": {}}},
        },
    ]

    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: snapshots.pop(0),
    )
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    req = api_router.RetrospectiveRespondRequest(
        days=7,
        fingerprint="gcf_resp_1",
        action="dismiss",
        context="instinct_escape",
    )
    payload = asyncio.run(api_router.respond_retrospective_intervention(req))

    assert payload["status"] == "responded"
    assert payload["action"] == "dismiss"
    assert emitted and emitted[0]["type"] == "guardian_intervention_responded"
    assert emitted[0]["payload"]["fingerprint"] == "gcf_resp_1"
    assert emitted[0]["payload"]["context"] == "instinct_escape"


def test_respond_retrospective_intervention_rejects_invalid_context(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_ctx",
                "latest": None,
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_ctx",
            },
            "authority": {"safe_mode": {"active": False, "recommendation": {}}},
        },
    )
    req = api_router.RetrospectiveRespondRequest(
        days=7,
        fingerprint="gcf_ctx",
        action="dismiss",
        context="invalid_context",
    )
    try:
        asyncio.run(api_router.respond_retrospective_intervention(req))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        assert False, "Expected 400 for invalid guardian response context"


def test_respond_retrospective_intervention_can_enter_safe_mode(monkeypatch):
    emitted = []
    snapshots = [
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_safe_1",
                "latest": None,
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_safe_1",
            },
            "authority": {"safe_mode": {"active": False, "recommendation": {}}},
        },
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_safe_1",
                "latest": {
                    "action": "dismiss",
                    "fingerprint": "gcf_safe_1",
                    "timestamp": "2026-02-11T12:10:00",
                },
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_safe_1",
            },
            "authority": {
                "safe_mode": {
                    "active": False,
                    "cooldown_complete": True,
                    "recommendation": {
                        "should_enter": True,
                        "should_exit": False,
                        "reason": "high_resistance_low_follow_through",
                        "response_count": 4,
                        "resistance_count": 4,
                        "confirmation_ratio": 0.0,
                    },
                }
            },
        },
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_safe_1",
                "latest": {
                    "action": "dismiss",
                    "fingerprint": "gcf_safe_1",
                    "timestamp": "2026-02-11T12:10:00",
                },
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_safe_1",
            },
            "authority": {
                "safe_mode": {
                    "active": True,
                    "entered_at": "2026-02-11T12:11:00",
                    "recommendation": {"should_enter": False, "should_exit": False},
                }
            },
        },
    ]

    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: snapshots.pop(0),
    )
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    req = api_router.RetrospectiveRespondRequest(
        days=7,
        fingerprint="gcf_safe_1",
        action="dismiss",
    )
    payload = asyncio.run(api_router.respond_retrospective_intervention(req))

    assert payload["status"] == "responded"
    assert payload["safe_mode_transition"] == "entered"
    assert any(event["type"] == "guardian_safe_mode_entered" for event in emitted)


def test_respond_retrospective_confirm_works_in_soft_mode(monkeypatch):
    emitted = []
    snapshots = [
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_soft_confirm",
                "latest": None,
            },
            "confirmation_action": {
                "required": False,
                "confirmed": False,
                "fingerprint": "gcf_soft_confirm",
            },
            "authority": {"safe_mode": {"active": False, "recommendation": {}}},
        },
        {
            "period": {"days": 7},
            "suggestion": "keep focus",
            "display": True,
            "require_confirm": False,
            "suggestion_sources": [{"signal": "repeated_skip"}],
            "response_action": {
                "required": False,
                "pending": False,
                "fingerprint": "gcf_soft_confirm",
                "latest": {
                    "action": "confirm",
                    "fingerprint": "gcf_soft_confirm",
                    "timestamp": "2026-02-11T12:10:00",
                },
            },
            "confirmation_action": {
                "required": False,
                "confirmed": True,
                "fingerprint": "gcf_soft_confirm",
            },
            "authority": {"safe_mode": {"active": False, "recommendation": {}}},
        },
    ]
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: snapshots.pop(0),
    )
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))

    req = api_router.RetrospectiveRespondRequest(
        days=7,
        fingerprint="gcf_soft_confirm",
        action="confirm",
    )
    payload = asyncio.run(api_router.respond_retrospective_intervention(req))

    assert payload["status"] == "confirmed"
    assert emitted and emitted[0]["type"] == "guardian_intervention_confirmed"


def test_start_l2_session_appends_event(monkeypatch):
    emitted = []
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {"l2_session": {"active_session": True, "active_session_id": "sess_1"}},
    )

    req = api_router.L2SessionActionRequest(
        session_id="sess_1",
        note="deep work",
        intention="Finish the proposal draft section.",
    )
    payload = asyncio.run(api_router.start_l2_session(req))

    assert payload["status"] == "started"
    assert payload["session_id"] == "sess_1"
    assert emitted and emitted[0]["type"] == "l2_session_started"
    assert emitted[0]["payload"]["session_id"] == "sess_1"
    assert emitted[0]["payload"]["intention"] == "Finish the proposal draft section."


def test_resume_l2_session_appends_event(monkeypatch):
    emitted = []
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))
    monkeypatch.setattr(api_router, "_resolve_resumable_l2_session_id", lambda: "sess_2")
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {"l2_session": {"active_session": True, "active_session_id": "sess_2"}},
    )

    req = api_router.L2SessionActionRequest(resume_step="Re-enter by executing first TODO.")
    payload = asyncio.run(api_router.resume_l2_session(req))

    assert payload["status"] == "resumed"
    assert payload["session_id"] == "sess_2"
    assert emitted and emitted[0]["type"] == "l2_session_resumed"
    assert emitted[0]["payload"]["resume_step"] == "Re-enter by executing first TODO."


def test_resume_l2_session_requires_interrupt(monkeypatch):
    monkeypatch.setattr(api_router, "_resolve_resumable_l2_session_id", lambda: None)

    req = api_router.L2SessionActionRequest()
    try:
        asyncio.run(api_router.resume_l2_session(req))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        assert False, "Expected 400 when no interrupted L2 session is available"


def test_interrupt_l2_session_appends_event(monkeypatch):
    emitted = []
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {"l2_session": {"active_session": False, "active_session_id": None}},
    )

    req = api_router.L2SessionActionRequest(session_id="sess_2", reason="energy_drop")
    payload = asyncio.run(api_router.interrupt_l2_session(req))

    assert payload["status"] == "interrupted"
    assert payload["session_id"] == "sess_2"
    assert payload["reason"] == "energy_drop"
    assert emitted and emitted[0]["type"] == "l2_session_interrupted"
    assert emitted[0]["payload"]["reason"] == "energy_drop"


def test_interrupt_l2_session_rejects_invalid_reason(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {"l2_session": {"active_session": True, "active_session_id": "sess_x"}},
    )
    req = api_router.L2SessionActionRequest(reason="invalid_reason")
    try:
        asyncio.run(api_router.interrupt_l2_session(req))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        assert False, "Expected 400 for invalid l2 interrupt reason"


def test_complete_l2_session_requires_active_session(monkeypatch):
    monkeypatch.setattr(api_router, "_resolve_active_l2_session_id", lambda: None)
    req = api_router.L2SessionActionRequest()
    try:
        asyncio.run(api_router.complete_l2_session(req))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        assert False, "Expected 400 when no active L2 session is available"


def test_complete_l2_session_appends_reflection(monkeypatch):
    emitted = []
    monkeypatch.setattr(api_router, "append_event", lambda event: emitted.append(event))
    monkeypatch.setattr(api_router, "_resolve_active_l2_session_id", lambda: "sess_3")
    monkeypatch.setattr(
        api_router,
        "build_guardian_retrospective_response",
        lambda days=7: {"l2_session": {"active_session": False, "active_session_id": None}},
    )
    req = api_router.L2SessionActionRequest(reflection="Closed the hardest part first.")
    payload = asyncio.run(api_router.complete_l2_session(req))

    assert payload["status"] == "completed"
    assert payload["session_id"] == "sess_3"
    assert emitted and emitted[0]["type"] == "l2_session_completed"
    assert emitted[0]["payload"]["reflection"] == "Closed the hardest part first."


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
