import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import yaml

from core.blueprint_anchor import AnchorManager
from core.event_sourcing import EVENT_LOG_PATH, EVENT_SCHEMA_VERSION, append_event
from core.feedback_classifier import classify_feedback
from core.goal_service import GoalService
from core.interaction_handler import InteractionHandler
from core.llm_adapter import get_llm
from core.objective_engine.models import GoalState
from core.objective_engine.registry import GoalRegistry
from core.retrospective import build_guardian_retrospective_response
from core.snapshot_manager import create_snapshot
from core.steward import Steward
from core.utils import parse_llm_json
from scheduler.daily_tick import ensure_tick_applied

router = APIRouter()


class VisionUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class FeedbackRequest(BaseModel):
    message: str


class InteractionRequest(BaseModel):
    message: str


class ActionRequest(BaseModel):
    action: str  # complete, skip, start
    reason: Optional[str] = None


class RetrospectiveConfirmRequest(BaseModel):
    days: int = 7
    fingerprint: Optional[str] = None
    note: Optional[str] = None
    context: Optional[str] = None


class RetrospectiveRespondRequest(BaseModel):
    days: int = 7
    fingerprint: Optional[str] = None
    action: str = "confirm"
    note: Optional[str] = None
    context: Optional[str] = None


class L2SessionActionRequest(BaseModel):
    session_id: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None
    intention: Optional[str] = None
    resume_step: Optional[str] = None
    reflection: Optional[str] = None


class AnchorActivateRequest(BaseModel):
    force: bool = False


class GuardianDeviationThresholdsRequest(BaseModel):
    repeated_skip: int = 2
    l2_interruption: int = 1
    stagnation_days: int = 3


class GuardianL2ThresholdsRequest(BaseModel):
    high: float = 0.75
    medium: float = 0.50


class GuardianEscalationConfigRequest(BaseModel):
    window_days: int = 7
    firm_reminder_resistance: int = 2
    periodic_check_resistance: int = 4


class GuardianSafeModeConfigRequest(BaseModel):
    enabled: bool = True
    resistance_threshold: int = 5
    min_response_events: int = 3
    max_confirmation_ratio: float = 0.34
    recovery_confirmations: int = 2
    cooldown_hours: int = 24


class GuardianAuthorityConfigRequest(BaseModel):
    escalation: GuardianEscalationConfigRequest = Field(
        default_factory=GuardianEscalationConfigRequest
    )
    safe_mode: GuardianSafeModeConfigRequest = Field(default_factory=GuardianSafeModeConfigRequest)


class GuardianConfigUpdateRequest(BaseModel):
    intervention_level: Optional[str] = None
    deviation_signals: GuardianDeviationThresholdsRequest
    l2_protection: GuardianL2ThresholdsRequest
    authority: Optional[GuardianAuthorityConfigRequest] = None


class GuardianAutoTuneTriggerConfigRequest(BaseModel):
    lookback_days: int = 7
    min_event_count: int = 20
    cooldown_hours: int = 24


class GuardianAutoTuneGuardrailsConfigRequest(BaseModel):
    max_int_step: int = 1
    max_float_step: float = 0.05
    min_confidence: float = 0.55


class GuardianAutoTuneConfigUpdateRequest(BaseModel):
    enabled: bool = False
    mode: str = "shadow"
    llm_enabled: bool = True
    trigger: GuardianAutoTuneTriggerConfigRequest = Field(
        default_factory=GuardianAutoTuneTriggerConfigRequest
    )
    guardrails: GuardianAutoTuneGuardrailsConfigRequest = Field(
        default_factory=GuardianAutoTuneGuardrailsConfigRequest
    )


class GuardianAutoTuneRunRequest(BaseModel):
    trigger: str = "manual"


def get_steward() -> Steward:
    state = ensure_tick_applied()
    registry = GoalRegistry()
    return Steward(state, registry)


def get_goal_service() -> GoalService:
    return GoalService()


BLUEPRINT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "concepts"
    / "better_human_blueprint.md"
)
BLUEPRINT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "blueprint.yaml"
ALLOWED_INTERVENTION_LEVELS = {"OBSERVE_ONLY", "SOFT", "ASK"}
ALLOWED_GUARDIAN_RESPONSE_ACTIONS = {"confirm", "snooze", "dismiss"}
ALLOWED_GUARDIAN_RESPONSE_CONTEXTS = {
    "recovering",
    "resource_blocked",
    "task_too_big",
    "instinct_escape",
}
ALLOWED_L2_SESSION_INTERRUPT_REASONS = {
    "context_switch",
    "external_interrupt",
    "energy_drop",
    "tooling_blocked",
    "other",
}
ALLOWED_GUARDIAN_AUTOTUNE_MODES = {"shadow"}


def _coerce_int(value: Any, default: int, min_value: int = 1, max_value: int = 365) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


def _coerce_float(
    value: Any,
    default: float,
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


def _guardian_config_defaults() -> Dict[str, Any]:
    return {
        "intervention_level": "SOFT",
        "thresholds": {
            "deviation_signals": {
                "repeated_skip": 2,
                "l2_interruption": 1,
                "stagnation_days": 3,
            },
            "l2_protection": {"high": 0.75, "medium": 0.50},
        },
        "authority": {
            "escalation": {
                "window_days": 7,
                "firm_reminder_resistance": 2,
                "periodic_check_resistance": 4,
            },
            "safe_mode": {
                "enabled": True,
                "resistance_threshold": 5,
                "min_response_events": 3,
                "max_confirmation_ratio": 0.34,
                "recovery_confirmations": 2,
                "cooldown_hours": 24,
            },
        },
    }


def _guardian_autotune_defaults() -> Dict[str, Any]:
    return {
        "enabled": False,
        "mode": "shadow",
        "llm_enabled": True,
        "trigger": {
            "lookback_days": 7,
            "min_event_count": 20,
            "cooldown_hours": 24,
        },
        "guardrails": {
            "max_int_step": 1,
            "max_float_step": 0.05,
            "min_confidence": 0.55,
        },
    }


def _load_blueprint_yaml() -> Dict[str, Any]:
    if not BLUEPRINT_CONFIG_PATH.exists():
        return {}
    try:
        with open(BLUEPRINT_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalized_guardian_config(raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    defaults = _guardian_config_defaults()
    raw = raw if isinstance(raw, dict) else {}

    intervention_level = str(raw.get("intervention_level", defaults["intervention_level"])).upper()
    if intervention_level not in ALLOWED_INTERVENTION_LEVELS:
        intervention_level = defaults["intervention_level"]

    raw_thresholds = raw.get("guardian_thresholds", {})
    if not isinstance(raw_thresholds, dict):
        raw_thresholds = {}
    raw_deviation = raw_thresholds.get("deviation_signals", {})
    if not isinstance(raw_deviation, dict):
        raw_deviation = {}
    raw_l2 = raw_thresholds.get("l2_protection", {})
    if not isinstance(raw_l2, dict):
        raw_l2 = {}

    repeated_skip = _coerce_int(
        raw_deviation.get("repeated_skip"),
        defaults["thresholds"]["deviation_signals"]["repeated_skip"],
    )
    l2_interruption = _coerce_int(
        raw_deviation.get("l2_interruption"),
        defaults["thresholds"]["deviation_signals"]["l2_interruption"],
    )
    stagnation_days = _coerce_int(
        raw_deviation.get("stagnation_days"),
        defaults["thresholds"]["deviation_signals"]["stagnation_days"],
    )
    l2_high = _coerce_float(raw_l2.get("high"), defaults["thresholds"]["l2_protection"]["high"])
    l2_medium = _coerce_float(
        raw_l2.get("medium"),
        defaults["thresholds"]["l2_protection"]["medium"],
    )
    if l2_medium > l2_high:
        l2_medium = l2_high

    raw_authority = raw.get("guardian_authority", {})
    if not isinstance(raw_authority, dict):
        raw_authority = {}
    raw_escalation = raw_authority.get("escalation", {})
    if not isinstance(raw_escalation, dict):
        raw_escalation = {}
    raw_safe_mode = raw_authority.get("safe_mode", {})
    if not isinstance(raw_safe_mode, dict):
        raw_safe_mode = {}

    escalation_window_days = _coerce_int(
        raw_escalation.get("window_days"),
        defaults["authority"]["escalation"]["window_days"],
        min_value=1,
        max_value=30,
    )
    firm_reminder_resistance = _coerce_int(
        raw_escalation.get("firm_reminder_resistance"),
        defaults["authority"]["escalation"]["firm_reminder_resistance"],
        min_value=1,
        max_value=99,
    )
    periodic_check_resistance = _coerce_int(
        raw_escalation.get("periodic_check_resistance"),
        defaults["authority"]["escalation"]["periodic_check_resistance"],
        min_value=1,
        max_value=99,
    )
    if periodic_check_resistance < firm_reminder_resistance:
        periodic_check_resistance = firm_reminder_resistance

    raw_enabled = raw_safe_mode.get("enabled", defaults["authority"]["safe_mode"]["enabled"])
    if isinstance(raw_enabled, str):
        safe_mode_enabled = raw_enabled.strip().lower() in {"1", "true", "yes", "on"}
    else:
        safe_mode_enabled = bool(raw_enabled)
    resistance_threshold = _coerce_int(
        raw_safe_mode.get("resistance_threshold"),
        defaults["authority"]["safe_mode"]["resistance_threshold"],
        min_value=1,
        max_value=999,
    )
    min_response_events = _coerce_int(
        raw_safe_mode.get("min_response_events"),
        defaults["authority"]["safe_mode"]["min_response_events"],
        min_value=1,
        max_value=999,
    )
    max_confirmation_ratio = _coerce_float(
        raw_safe_mode.get("max_confirmation_ratio"),
        defaults["authority"]["safe_mode"]["max_confirmation_ratio"],
        min_value=0.0,
        max_value=1.0,
    )
    recovery_confirmations = _coerce_int(
        raw_safe_mode.get("recovery_confirmations"),
        defaults["authority"]["safe_mode"]["recovery_confirmations"],
        min_value=1,
        max_value=999,
    )
    cooldown_hours = _coerce_int(
        raw_safe_mode.get("cooldown_hours"),
        defaults["authority"]["safe_mode"]["cooldown_hours"],
        min_value=1,
        max_value=720,
    )

    return {
        "intervention_level": intervention_level,
        "thresholds": {
            "deviation_signals": {
                "repeated_skip": repeated_skip,
                "l2_interruption": l2_interruption,
                "stagnation_days": stagnation_days,
            },
            "l2_protection": {"high": round(l2_high, 2), "medium": round(l2_medium, 2)},
        },
        "authority": {
            "escalation": {
                "window_days": escalation_window_days,
                "firm_reminder_resistance": firm_reminder_resistance,
                "periodic_check_resistance": periodic_check_resistance,
            },
            "safe_mode": {
                "enabled": safe_mode_enabled,
                "resistance_threshold": resistance_threshold,
                "min_response_events": min_response_events,
                "max_confirmation_ratio": round(max_confirmation_ratio, 2),
                "recovery_confirmations": recovery_confirmations,
                "cooldown_hours": cooldown_hours,
            },
        },
    }


def _normalized_guardian_autotune_config(raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    defaults = _guardian_autotune_defaults()
    raw = raw if isinstance(raw, dict) else {}
    raw_autotune = raw.get("guardian_autotune", {})
    if not isinstance(raw_autotune, dict):
        raw_autotune = {}

    mode = str(raw_autotune.get("mode", defaults["mode"])).strip().lower()
    if mode not in ALLOWED_GUARDIAN_AUTOTUNE_MODES:
        mode = defaults["mode"]

    raw_trigger = raw_autotune.get("trigger", {})
    if not isinstance(raw_trigger, dict):
        raw_trigger = {}
    raw_guardrails = raw_autotune.get("guardrails", {})
    if not isinstance(raw_guardrails, dict):
        raw_guardrails = {}

    return {
        "enabled": bool(raw_autotune.get("enabled", defaults["enabled"])),
        "mode": mode,
        "llm_enabled": bool(raw_autotune.get("llm_enabled", defaults["llm_enabled"])),
        "trigger": {
            "lookback_days": _coerce_int(
                raw_trigger.get("lookback_days"),
                defaults["trigger"]["lookback_days"],
                min_value=1,
                max_value=30,
            ),
            "min_event_count": _coerce_int(
                raw_trigger.get("min_event_count"),
                defaults["trigger"]["min_event_count"],
                min_value=1,
                max_value=9999,
            ),
            "cooldown_hours": _coerce_int(
                raw_trigger.get("cooldown_hours"),
                defaults["trigger"]["cooldown_hours"],
                min_value=1,
                max_value=168,
            ),
        },
        "guardrails": {
            "max_int_step": _coerce_int(
                raw_guardrails.get("max_int_step"),
                defaults["guardrails"]["max_int_step"],
                min_value=1,
                max_value=3,
            ),
            "max_float_step": round(
                _coerce_float(
                    raw_guardrails.get("max_float_step"),
                    defaults["guardrails"]["max_float_step"],
                    min_value=0.01,
                    max_value=0.2,
                ),
                2,
            ),
            "min_confidence": round(
                _coerce_float(
                    raw_guardrails.get("min_confidence"),
                    defaults["guardrails"]["min_confidence"],
                    min_value=0.0,
                    max_value=1.0,
                ),
                2,
            ),
        },
    }


def _save_guardian_config(config_payload: Dict[str, Any]) -> None:
    existing = _load_blueprint_yaml()
    if not isinstance(existing, dict):
        existing = {}
    existing["intervention_level"] = config_payload["intervention_level"]
    existing["guardian_thresholds"] = {
        "deviation_signals": config_payload["thresholds"]["deviation_signals"],
        "l2_protection": config_payload["thresholds"]["l2_protection"],
    }
    authority_payload = config_payload.get("authority") if isinstance(config_payload, dict) else {}
    if not isinstance(authority_payload, dict):
        authority_payload = {}
    existing["guardian_authority"] = {
        "escalation": authority_payload.get("escalation", {}),
        "safe_mode": authority_payload.get("safe_mode", {}),
    }
    BLUEPRINT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BLUEPRINT_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)


def _save_guardian_autotune_config(config_payload: Dict[str, Any]) -> None:
    existing = _load_blueprint_yaml()
    if not isinstance(existing, dict):
        existing = {}
    existing["guardian_autotune"] = {
        "enabled": bool(config_payload.get("enabled", False)),
        "mode": str(config_payload.get("mode", "shadow")).lower(),
        "llm_enabled": bool(config_payload.get("llm_enabled", True)),
        "trigger": (config_payload.get("trigger") if isinstance(config_payload, dict) else {})
        or {},
        "guardrails": (
            config_payload.get("guardrails") if isinstance(config_payload, dict) else {}
        )
        or {},
    }
    BLUEPRINT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BLUEPRINT_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)


def _anchor_payload(anchor) -> dict:
    if not anchor:
        return {
            "active": False,
            "version": None,
            "created_at": None,
            "confirmed_by_user": False,
            "non_negotiables_count": 0,
            "commitments_count": 0,
            "anti_values_count": 0,
            "instinct_adversaries_count": 0,
        }
    return {
        "active": True,
        "version": anchor.version,
        "created_at": anchor.created_at,
        "confirmed_by_user": bool(anchor.confirmed_by_user),
        "non_negotiables_count": len(anchor.non_negotiables or ()),
        "commitments_count": len(anchor.long_horizon_commitments or ()),
        "anti_values_count": len(anchor.anti_values or ()),
        "instinct_adversaries_count": len(anchor.instinct_adversaries or ()),
    }


def _anchor_diff_payload(diff) -> dict:
    return {
        "status": diff.status,
        "version_change": diff.version_change,
        "added_non_negotiables": sorted(list(diff.added_non_negotiables or set())),
        "removed_non_negotiables": sorted(list(diff.removed_non_negotiables or set())),
        "added_commitments": sorted(list(diff.added_commitments or set())),
        "removed_commitments": sorted(list(diff.removed_commitments or set())),
        "added_anti_values": sorted(list(diff.added_anti_values or set())),
        "removed_anti_values": sorted(list(diff.removed_anti_values or set())),
        "added_adversaries": sorted(list(diff.added_adversaries or set())),
        "removed_adversaries": sorted(list(diff.removed_adversaries or set())),
    }


def _load_latest_event(event_type: str) -> Optional[dict]:
    if not EVENT_LOG_PATH.exists():
        return None
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for raw in reversed(lines):
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == event_type:
            return event
    return None


def _parse_event_timestamp(raw_ts: Any) -> Optional[datetime]:
    if not isinstance(raw_ts, str) or not raw_ts.strip():
        return None
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _load_events_for_days(days: int) -> list:
    if not EVENT_LOG_PATH.exists():
        return []
    cutoff = datetime.now() - timedelta(days=max(1, int(days)))
    events = []
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ev_time = _parse_event_timestamp(event.get("timestamp"))
            if ev_time is None or ev_time >= cutoff:
                events.append(event)
    return events


def _clamp_step_int(
    *,
    current: int,
    target: Any,
    max_step: int,
    min_value: int,
    max_value: int,
) -> int:
    current_value = _coerce_int(current, current, min_value=min_value, max_value=max_value)
    target_value = _coerce_int(target, current_value, min_value=min_value, max_value=max_value)
    max_step = _coerce_int(max_step, 1, min_value=1, max_value=3)
    delta = max(-max_step, min(max_step, target_value - current_value))
    return _coerce_int(
        current_value + delta,
        current_value,
        min_value=min_value,
        max_value=max_value,
    )


def _clamp_step_float(
    *,
    current: float,
    target: Any,
    max_step: float,
    min_value: float,
    max_value: float,
) -> float:
    current_value = _coerce_float(current, current, min_value=min_value, max_value=max_value)
    target_value = _coerce_float(target, current_value, min_value=min_value, max_value=max_value)
    max_step = _coerce_float(max_step, 0.05, min_value=0.01, max_value=0.2)
    delta = max(-max_step, min(max_step, target_value - current_value))
    return round(
        _coerce_float(
            current_value + delta,
            current_value,
            min_value=min_value,
            max_value=max_value,
        ),
        2,
    )


def _deterministic_guardian_autotune_candidate(
    *,
    current_config: Dict[str, Any],
    retrospective: Dict[str, Any],
) -> Dict[str, Any]:
    deviation = (
        (current_config.get("thresholds") or {}).get("deviation_signals")
        if isinstance(current_config.get("thresholds"), dict)
        else {}
    )
    deviation = deviation if isinstance(deviation, dict) else {}
    l2 = (
        (current_config.get("thresholds") or {}).get("l2_protection")
        if isinstance(current_config.get("thresholds"), dict)
        else {}
    )
    l2 = l2 if isinstance(l2, dict) else {}

    metrics = retrospective.get("humanization_metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    friction = (
        metrics.get("friction_load")
        if isinstance(metrics.get("friction_load"), dict)
        else {}
    )
    recovery = (
        metrics.get("recovery_adoption_rate")
        if isinstance(metrics.get("recovery_adoption_rate"), dict)
        else {}
    )
    support = (
        metrics.get("support_vs_override")
        if isinstance(metrics.get("support_vs_override"), dict)
        else {}
    )
    l2_protection = retrospective.get("l2_protection") or {}
    if not isinstance(l2_protection, dict):
        l2_protection = {}

    friction_score = _coerce_float(friction.get("score"), 0.0, min_value=0.0, max_value=1.0)
    recovery_rate_raw = recovery.get("rate")
    support_ratio_raw = support.get("support_ratio")
    l2_ratio_raw = l2_protection.get("ratio")
    recovery_rate = (
        _coerce_float(recovery_rate_raw, 0.0, min_value=0.0, max_value=1.0)
        if isinstance(recovery_rate_raw, (int, float))
        else None
    )
    support_ratio = (
        _coerce_float(support_ratio_raw, 0.0, min_value=0.0, max_value=1.0)
        if isinstance(support_ratio_raw, (int, float))
        else None
    )
    l2_ratio = (
        _coerce_float(l2_ratio_raw, 0.0, min_value=0.0, max_value=1.0)
        if isinstance(l2_ratio_raw, (int, float))
        else None
    )

    repeated_skip = _coerce_int(deviation.get("repeated_skip"), 2, min_value=1, max_value=8)
    l2_interruption = _coerce_int(deviation.get("l2_interruption"), 1, min_value=1, max_value=6)
    stagnation_days = _coerce_int(deviation.get("stagnation_days"), 3, min_value=1, max_value=14)
    l2_high = _coerce_float(l2.get("high"), 0.75, min_value=0.55, max_value=0.95)
    l2_medium = _coerce_float(l2.get("medium"), 0.50, min_value=0.30, max_value=0.85)

    reason_bits = []
    target = {
        "repeated_skip": repeated_skip,
        "l2_interruption": l2_interruption,
        "stagnation_days": stagnation_days,
        "l2_high": l2_high,
        "l2_medium": l2_medium,
    }

    if friction_score >= 0.67 or (support_ratio is not None and support_ratio < 0.4):
        target["repeated_skip"] = repeated_skip + 1
        target["l2_interruption"] = l2_interruption + 1
        target["stagnation_days"] = stagnation_days + 1
        reason_bits.append("high friction or override-heavy pattern, easing sensitivity")
    elif (
        friction_score <= 0.33
        and recovery_rate is not None
        and recovery_rate >= 0.75
        and (support_ratio is None or support_ratio >= 0.6)
    ):
        target["repeated_skip"] = repeated_skip - 1
        target["stagnation_days"] = stagnation_days - 1
        reason_bits.append("stable follow-through, tightening sensitivity")

    if l2_ratio is not None:
        if l2_ratio >= l2_high + 0.1 and recovery_rate is not None and recovery_rate >= 0.7:
            target["l2_high"] = l2_high + 0.05
            target["l2_medium"] = l2_medium + 0.05
            reason_bits.append("strong l2 protection, raising quality bar")
        elif l2_ratio <= max(0.0, l2_medium - 0.1):
            target["l2_high"] = l2_high - 0.05
            target["l2_medium"] = l2_medium - 0.05
            reason_bits.append("weak l2 protection, lowering pressure temporarily")

    if target["l2_medium"] > target["l2_high"]:
        target["l2_medium"] = target["l2_high"]

    return {
        "candidate": target,
        "reason": "; ".join(reason_bits) if reason_bits else "metrics are stable",
        "confidence": 0.62 if reason_bits else 0.5,
        "source": "rules",
    }


def _llm_guardian_autotune_candidate(
    *,
    current_config: Dict[str, Any],
    retrospective: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    llm = get_llm("strategic_brain")
    if llm.get_model_name() == "rule_based":
        return None

    prompt_payload = {
        "current_thresholds": (current_config.get("thresholds") or {}),
        "humanization_metrics": retrospective.get("humanization_metrics", {}),
        "l2_protection": retrospective.get("l2_protection", {}),
        "deviation_signals": retrospective.get("deviation_signals", []),
    }
    prompt = (
        "You are tuning guardian thresholds in shadow mode.\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "reason": "string",\n'
        '  "confidence": 0.0,\n'
        '  "candidate": {\n'
        '    "repeated_skip": 0,\n'
        '    "l2_interruption": 0,\n'
        '    "stagnation_days": 0,\n'
        '    "l2_high": 0.0,\n'
        '    "l2_medium": 0.0\n'
        "  }\n"
        "}\n\n"
        f"Context:\n{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
    )
    try:
        response = llm.generate(
            prompt=prompt,
            system_prompt="Return strict JSON only. Keep changes conservative.",
            temperature=0.2,
            max_tokens=300,
        )
    except Exception:
        return None
    if not response.success or not response.content:
        return None
    parsed = parse_llm_json(response.content)
    if not isinstance(parsed, dict):
        return None
    candidate = parsed.get("candidate")
    if not isinstance(candidate, dict):
        return None
    return {
        "candidate": candidate,
        "reason": str(parsed.get("reason") or "llm_proposal"),
        "confidence": _coerce_float(parsed.get("confidence"), 0.0, min_value=0.0, max_value=1.0),
        "source": "llm",
    }


def _sanitize_guardian_autotune_candidate(
    *,
    current_config: Dict[str, Any],
    candidate: Dict[str, Any],
    guardrails: Dict[str, Any],
) -> Dict[str, Any]:
    thresholds = current_config.get("thresholds") if isinstance(current_config, dict) else {}
    thresholds = thresholds if isinstance(thresholds, dict) else {}
    raw_deviation = thresholds.get("deviation_signals")
    deviation = raw_deviation if isinstance(raw_deviation, dict) else {}
    raw_l2 = thresholds.get("l2_protection")
    l2 = raw_l2 if isinstance(raw_l2, dict) else {}
    max_int_step = _coerce_int(guardrails.get("max_int_step"), 1, min_value=1, max_value=3)
    max_float_step = _coerce_float(
        guardrails.get("max_float_step"),
        0.05,
        min_value=0.01,
        max_value=0.2,
    )

    sanitized = {
        "repeated_skip": _clamp_step_int(
            current=_coerce_int(deviation.get("repeated_skip"), 2, min_value=1, max_value=8),
            target=candidate.get("repeated_skip"),
            max_step=max_int_step,
            min_value=1,
            max_value=8,
        ),
        "l2_interruption": _clamp_step_int(
            current=_coerce_int(deviation.get("l2_interruption"), 1, min_value=1, max_value=6),
            target=candidate.get("l2_interruption"),
            max_step=max_int_step,
            min_value=1,
            max_value=6,
        ),
        "stagnation_days": _clamp_step_int(
            current=_coerce_int(deviation.get("stagnation_days"), 3, min_value=1, max_value=14),
            target=candidate.get("stagnation_days"),
            max_step=max_int_step,
            min_value=1,
            max_value=14,
        ),
        "l2_high": _clamp_step_float(
            current=_coerce_float(l2.get("high"), 0.75, min_value=0.55, max_value=0.95),
            target=candidate.get("l2_high"),
            max_step=max_float_step,
            min_value=0.55,
            max_value=0.95,
        ),
        "l2_medium": _clamp_step_float(
            current=_coerce_float(l2.get("medium"), 0.50, min_value=0.30, max_value=0.85),
            target=candidate.get("l2_medium"),
            max_step=max_float_step,
            min_value=0.30,
            max_value=0.85,
        ),
    }
    if sanitized["l2_medium"] > sanitized["l2_high"]:
        sanitized["l2_medium"] = sanitized["l2_high"]
    return sanitized


def _build_autotune_patch(
    *,
    current_config: Dict[str, Any],
    sanitized_candidate: Dict[str, Any],
) -> Dict[str, Any]:
    thresholds = current_config.get("thresholds") if isinstance(current_config, dict) else {}
    thresholds = thresholds if isinstance(thresholds, dict) else {}
    raw_deviation = thresholds.get("deviation_signals")
    deviation = raw_deviation if isinstance(raw_deviation, dict) else {}
    raw_l2 = thresholds.get("l2_protection")
    l2 = raw_l2 if isinstance(raw_l2, dict) else {}
    current_flat = {
        "repeated_skip": _coerce_int(
            deviation.get("repeated_skip"),
            2,
            min_value=1,
            max_value=8,
        ),
        "l2_interruption": _coerce_int(
            deviation.get("l2_interruption"),
            1,
            min_value=1,
            max_value=6,
        ),
        "stagnation_days": _coerce_int(
            deviation.get("stagnation_days"),
            3,
            min_value=1,
            max_value=14,
        ),
        "l2_high": round(
            _coerce_float(l2.get("high"), 0.75, min_value=0.55, max_value=0.95),
            2,
        ),
        "l2_medium": round(
            _coerce_float(l2.get("medium"), 0.50, min_value=0.30, max_value=0.85),
            2,
        ),
    }
    patch = {}
    for key, current_val in current_flat.items():
        target_val = sanitized_candidate.get(key, current_val)
        if target_val != current_val:
            patch[key] = {"from": current_val, "to": target_val}
    return patch


def _run_guardian_autotune_shadow(trigger: str = "manual") -> Dict[str, Any]:
    now = datetime.now()
    raw = _load_blueprint_yaml()
    config_payload = _normalized_guardian_autotune_config(raw)
    if not config_payload.get("enabled"):
        return {"status": "disabled", "mode": "shadow", "reason": "autotune_disabled"}
    if config_payload.get("mode") != "shadow":
        return {
            "status": "skipped",
            "mode": config_payload.get("mode"),
            "reason": "unsupported_mode",
        }

    cooldown_hours = _coerce_int(
        (config_payload.get("trigger") or {}).get("cooldown_hours"),
        24,
        min_value=1,
        max_value=168,
    )
    latest = _load_latest_event("guardian_autotune_shadow_proposed")
    latest_time = _parse_event_timestamp((latest or {}).get("timestamp"))
    if latest_time and now - latest_time < timedelta(hours=cooldown_hours):
        return {
            "status": "skipped",
            "mode": "shadow",
            "reason": "cooldown_active",
            "cooldown_hours": cooldown_hours,
            "next_eligible_at": (latest_time + timedelta(hours=cooldown_hours)).isoformat(),
        }

    lookback_days = _coerce_int(
        (config_payload.get("trigger") or {}).get("lookback_days"),
        7,
        min_value=1,
        max_value=30,
    )
    min_event_count = _coerce_int(
        (config_payload.get("trigger") or {}).get("min_event_count"),
        20,
        min_value=1,
        max_value=9999,
    )
    events = _load_events_for_days(lookback_days)
    if len(events) < min_event_count:
        return {
            "status": "skipped",
            "mode": "shadow",
            "reason": "insufficient_event_volume",
            "event_count": len(events),
            "required_event_count": min_event_count,
        }

    current_config = _normalized_guardian_config(raw)
    retrospective = build_guardian_retrospective_response(days=lookback_days)
    guardrails = (
        config_payload.get("guardrails")
        if isinstance(config_payload.get("guardrails"), dict)
        else {}
    )
    deterministic = _deterministic_guardian_autotune_candidate(
        current_config=current_config,
        retrospective=retrospective,
    )
    selected = deterministic
    if config_payload.get("llm_enabled"):
        llm_candidate = _llm_guardian_autotune_candidate(
            current_config=current_config,
            retrospective=retrospective,
        )
        min_confidence = _coerce_float(
            guardrails.get("min_confidence"),
            0.55,
            min_value=0.0,
            max_value=1.0,
        )
        if llm_candidate and llm_candidate.get("confidence", 0.0) >= min_confidence:
            selected = llm_candidate

    sanitized_candidate = _sanitize_guardian_autotune_candidate(
        current_config=current_config,
        candidate=selected.get("candidate") if isinstance(selected.get("candidate"), dict) else {},
        guardrails=guardrails,
    )
    patch = _build_autotune_patch(
        current_config=current_config,
        sanitized_candidate=sanitized_candidate,
    )
    if not patch:
        return {
            "status": "skipped",
            "mode": "shadow",
            "reason": "no_effective_delta",
            "candidate_source": selected.get("source"),
        }

    proposal = {
        "trigger": str(trigger or "manual"),
        "lookback_days": lookback_days,
        "event_count": len(events),
        "candidate_source": selected.get("source"),
        "confidence": round(
            _coerce_float(selected.get("confidence"), 0.0, min_value=0.0, max_value=1.0),
            2,
        ),
        "reason": str(selected.get("reason") or ""),
        "patch": patch,
        "proposed_thresholds": {
            "deviation_signals": {
                "repeated_skip": sanitized_candidate["repeated_skip"],
                "l2_interruption": sanitized_candidate["l2_interruption"],
                "stagnation_days": sanitized_candidate["stagnation_days"],
            },
            "l2_protection": {
                "high": sanitized_candidate["l2_high"],
                "medium": sanitized_candidate["l2_medium"],
            },
        },
        "current_thresholds": current_config.get("thresholds", {}),
    }
    append_event(
        {
            "type": "guardian_autotune_shadow_proposed",
            "timestamp": now.isoformat(),
            "payload": proposal,
        }
    )
    return {
        "status": "proposed",
        "mode": "shadow",
        "proposal": proposal,
    }


def _has_review_due_this_week() -> bool:
    if not EVENT_LOG_PATH.exists():
        return False
    from datetime import timedelta

    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("type") != "review_due":
                    continue
                timestamp = event.get("timestamp") or ""
                date_raw = event.get("date") or timestamp[:10]
                if not date_raw:
                    continue
                event_date = datetime.strptime(date_raw[:10], "%Y-%m-%d").date()
                if week_start <= event_date <= week_end:
                    return True
            except (json.JSONDecodeError, ValueError):
                continue
    return False


def _normalized_audit(
    raw_audit: Optional[dict],
    default_strategy: str,
    default_trigger: str,
    default_constraint: str = "",
    default_risk: str = "",
) -> dict:
    audit = raw_audit if isinstance(raw_audit, dict) else {}
    decision_reason = audit.get("decision_reason", {})
    if not isinstance(decision_reason, dict):
        decision_reason = {}

    used_state_fields = audit.get("used_state_fields", [])
    if not isinstance(used_state_fields, list):
        used_state_fields = []

    normalized = {
        "strategy": audit.get("strategy") or default_strategy,
        "used_state_fields": used_state_fields,
        "decision_reason": {
            "trigger": decision_reason.get("trigger") or default_trigger,
            "constraint": decision_reason.get("constraint") or default_constraint,
            "risk": decision_reason.get("risk") or default_risk,
        },
    }
    # Preserve extension fields used by planner-level guards (e.g., Anchor).
    for extra_key in ("anchor",):
        if extra_key in audit:
            normalized[extra_key] = audit.get(extra_key)
    return normalized


@router.get("/state")
async def get_state():
    steward = get_steward()
    service = get_goal_service()
    system_state = steward.state
    registry = steward.registry

    identity = system_state.get("identity") or {}
    active_tasks = [
        task.__dict__
        for task in system_state.get("tasks", [])
        if str(getattr(task.status, "value", task.status)) == "pending"
    ]

    state_audit = _normalized_audit(
        raw_audit={
            "strategy": "state_projection",
            "used_state_fields": [
                "identity",
                "rhythm",
                "tasks",
                "goal_registry",
                "event_log.review_due",
                "anchor.current",
                "retrospective.alignment.trend",
                "retrospective.l2_protection",
                "retrospective.l2_session",
                "retrospective.guardian_role",
                "retrospective.intervention_policy",
                "retrospective.humanization_metrics",
                "retrospective.north_star_metrics",
                "retrospective.blueprint_narrative",
            ],
            "decision_reason": {
                "trigger": "State requested by API client",
                "constraint": "Read-model projection only",
                "risk": "Stale reads if filesystem is modified externally",
            },
        },
        default_strategy="state_projection",
        default_trigger="State requested by API client",
    )
    retrospective = build_guardian_retrospective_response(days=7)
    guardian_state = system_state.get("guardian") or {}
    guardian_autotune = _normalized_guardian_autotune_config(_load_blueprint_yaml())
    alignment_summary = service.summarize_alignment(registry.objectives + registry.goals)
    alignment_trend = (retrospective.get("alignment") or {}).get("trend", {})
    l2_protection = retrospective.get("l2_protection") or {}
    l2_session = retrospective.get("l2_session") or {}
    blueprint_narrative = retrospective.get("blueprint_narrative") or {}
    humanization_metrics = retrospective.get("humanization_metrics") or {}
    if not isinstance(humanization_metrics, dict):
        humanization_metrics = {}
    north_star_metrics = retrospective.get("north_star_metrics") or {}
    if not isinstance(north_star_metrics, dict):
        north_star_metrics = {}
    recovery_metric = humanization_metrics.get("recovery_adoption_rate")
    if not isinstance(recovery_metric, dict):
        recovery_metric = {}
    mundane_metric = (
        north_star_metrics.get("mundane_automation_coverage")
        if isinstance(north_star_metrics.get("mundane_automation_coverage"), dict)
        else {}
    )
    trust_metric = (
        north_star_metrics.get("human_trust_index")
        if isinstance(north_star_metrics.get("human_trust_index"), dict)
        else {}
    )
    l2_bloom_metric = (
        north_star_metrics.get("l2_bloom_hours")
        if isinstance(north_star_metrics.get("l2_bloom_hours"), dict)
        else {}
    )
    alignment_delta_metric = (
        north_star_metrics.get("alignment_delta_weekly")
        if isinstance(north_star_metrics.get("alignment_delta_weekly"), dict)
        else {}
    )
    north_star_targets = (
        north_star_metrics.get("targets_met")
        if isinstance(north_star_metrics.get("targets_met"), dict)
        else {}
    )
    guardian_authority = retrospective.get("authority") or {}
    guardian_escalation = (
        guardian_authority.get("escalation")
        if isinstance(guardian_authority, dict)
        else {}
    )
    if not isinstance(guardian_escalation, dict):
        guardian_escalation = {}
    guardian_safe_mode = (
        guardian_authority.get("safe_mode")
        if isinstance(guardian_authority, dict)
        else {}
    )
    if not isinstance(guardian_safe_mode, dict):
        guardian_safe_mode = {}
    anchor_snapshot = _anchor_payload(None)
    try:
        anchor = AnchorManager().get_current()
        if anchor:
            anchor_snapshot = _anchor_payload(anchor)
    except Exception:
        pass

    return {
        "identity": identity,
        "metrics": system_state.get("rhythm") or {},
        "energy_phase": steward.get_current_phase(),
        "active_tasks": active_tasks,
        "visions": [service.node_to_dict(v) for v in registry.visions],
        "objectives": [service.node_to_dict(o) for o in registry.objectives],
        "goals": [service.node_to_dict(g) for g in registry.goals],
        "pending_confirmation": [
            service.node_to_dict(g)
            for g in (registry.objectives + registry.goals)
            if g.state == GoalState.VISION_PENDING_CONFIRMATION
        ],
        "system_health": {
            "status": "nominal",
            "queue_load": len(active_tasks),
        },
        "weekly_review_due": _has_review_due_this_week(),
        "anchor": anchor_snapshot,
        "alignment": {
            "goal_summary": alignment_summary,
            "weekly_trend": alignment_trend,
        },
        "guardian": {
            "intervention_level": retrospective.get("intervention_level"),
            "pending_confirmation": bool(retrospective.get("require_confirm")),
            "confirmation_action": retrospective.get("confirmation_action", {}),
            "response_action": retrospective.get("response_action", {}),
            "guardian_role": retrospective.get("guardian_role", {}),
            "policy": retrospective.get("intervention_policy", {}),
            "blueprint_narrative": blueprint_narrative,
            "explainability": retrospective.get("explainability", {}),
            "autotune": guardian_autotune,
            "authority": guardian_authority,
            "escalation_stage": guardian_escalation.get("stage"),
            "safe_mode": guardian_safe_mode,
            "last_intervention_confirmation": guardian_state.get(
                "last_intervention_confirmation"
            ),
            "last_intervention_response": guardian_state.get("last_intervention_response"),
            "metrics": {
                "l2_protection_rate": l2_protection.get("ratio"),
                "l2_protection_level": l2_protection.get("level"),
                "l2_protection_summary": l2_protection.get("summary"),
                "l2_protection_trend": l2_protection.get("trend", []),
                "l2_protection_thresholds": l2_protection.get("thresholds", {}),
                "recovery_adoption_rate": recovery_metric.get("rate"),
                "friction_load": humanization_metrics.get("friction_load", {}),
                "support_vs_override": humanization_metrics.get(
                    "support_vs_override",
                    {},
                ),
                "north_star": north_star_metrics,
                "mundane_automation_coverage": mundane_metric.get("rate"),
                "l2_bloom_hours": l2_bloom_metric.get("hours"),
                "human_trust_index": trust_metric.get("score"),
                "alignment_delta_weekly": alignment_delta_metric.get("delta"),
                "north_star_targets_met": north_star_targets,
                "humanization": humanization_metrics,
                "l2_session": l2_session,
                "l2_completion_rate": l2_session.get("completion_rate"),
                "l2_recovery_rate": l2_session.get("recovery_rate"),
                "l2_resume_ready": l2_session.get("resume_ready"),
                "l2_resume_session_id": l2_session.get("resume_session_id"),
                "l2_micro_ritual": l2_session.get("micro_ritual", {}),
            },
        },
        "audit": state_audit,
        "meta": {
            "event_schema_version": EVENT_SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(),
        },
    }


@router.get("/retrospective")
async def get_retrospective(days: int = 7):
    return build_guardian_retrospective_response(days)


def _normalize_guardian_response_action(raw_action: Optional[str]) -> str:
    action = str(raw_action or "confirm").strip().lower()
    if action not in ALLOWED_GUARDIAN_RESPONSE_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail="action must be one of confirm | snooze | dismiss",
        )
    return action


def _normalize_guardian_response_context(raw_context: Optional[str]) -> Optional[str]:
    context = str(raw_context or "").strip().lower()
    if not context:
        return None
    if context not in ALLOWED_GUARDIAN_RESPONSE_CONTEXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "context must be one of recovering | resource_blocked | "
                "task_too_big | instinct_escape"
            ),
        )
    return context


def _guardian_recovery_step(
    *,
    action: str,
    context: Optional[str],
    suggestion: str,
) -> Optional[str]:
    normalized = str(context or "recovering").strip().lower()
    if action not in {"snooze", "dismiss"}:
        return None
    if normalized == "resource_blocked":
        return "先清理一个阻塞点（资源/信息/依赖），再回到主任务。"
    if normalized == "task_too_big":
        return "把当前任务拆成 10-20 分钟最小下一步，并仅执行第一步。"
    if normalized == "instinct_escape":
        return "先移除一个干扰源，然后进行 10 分钟保底执行。"
    if suggestion:
        return f"稍后重启建议：{suggestion}"
    return "先恢复状态，再完成一个 10 分钟最小动作。"


def _normalize_l2_interrupt_reason(raw_reason: Optional[str]) -> str:
    reason = str(raw_reason or "other").strip().lower()
    if reason not in ALLOWED_L2_SESSION_INTERRUPT_REASONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "reason must be one of context_switch | external_interrupt | "
                "energy_drop | tooling_blocked | other"
            ),
        )
    return reason


def _resolve_active_l2_session_id() -> Optional[str]:
    payload = build_guardian_retrospective_response(days=7)
    l2_session = payload.get("l2_session") if isinstance(payload.get("l2_session"), dict) else {}
    active_session_id = l2_session.get("active_session_id")
    return str(active_session_id) if active_session_id else None


def _resolve_resumable_l2_session_id() -> Optional[str]:
    payload = build_guardian_retrospective_response(days=7)
    l2_session = payload.get("l2_session") if isinstance(payload.get("l2_session"), dict) else {}
    resume_session_id = l2_session.get("resume_session_id")
    return str(resume_session_id) if resume_session_id else None


def _maybe_append_safe_mode_transition(
    *,
    days: int,
    payload: Dict[str, Any],
    fingerprint: Optional[str],
    source_action: str,
) -> Optional[str]:
    authority = payload.get("authority") if isinstance(payload, dict) else {}
    authority = authority if isinstance(authority, dict) else {}
    safe_mode = authority.get("safe_mode") if isinstance(authority, dict) else {}
    safe_mode = safe_mode if isinstance(safe_mode, dict) else {}
    recommendation = safe_mode.get("recommendation") if isinstance(safe_mode, dict) else {}
    recommendation = recommendation if isinstance(recommendation, dict) else {}

    should_enter = bool(recommendation.get("should_enter"))
    should_exit = bool(recommendation.get("should_exit"))
    is_active = bool(safe_mode.get("active"))
    reason = recommendation.get("reason") or "policy_transition"

    if should_enter and not is_active:
        append_event(
            {
                "type": "guardian_safe_mode_entered",
                "timestamp": datetime.now().isoformat(),
                "payload": {
                    "days": days,
                    "fingerprint": fingerprint,
                    "reason": reason,
                    "source_action": source_action,
                    "evidence": {
                        "response_count": recommendation.get("response_count"),
                        "resistance_count": recommendation.get("resistance_count"),
                        "confirmation_ratio": recommendation.get("confirmation_ratio"),
                    },
                },
            }
        )
        return "entered"

    if should_exit and is_active:
        append_event(
            {
                "type": "guardian_safe_mode_exited",
                "timestamp": datetime.now().isoformat(),
                "payload": {
                    "days": days,
                    "fingerprint": fingerprint,
                    "reason": reason,
                    "source_action": source_action,
                    "evidence": {
                        "confirmations_since_enter": recommendation.get(
                            "confirmations_since_enter"
                        ),
                        "cooldown_complete": safe_mode.get("cooldown_complete"),
                    },
                },
            }
        )
        return "exited"

    return None


def _apply_guardian_intervention_response(
    request: RetrospectiveRespondRequest,
    *,
    strict_confirm_required: bool = False,
) -> Dict[str, Any]:
    days = request.days or 7
    action = _normalize_guardian_response_action(request.action)
    context = _normalize_guardian_response_context(request.context)
    current_payload = build_guardian_retrospective_response(days)
    confirmation_action = (
        current_payload.get("confirmation_action")
        if isinstance(current_payload.get("confirmation_action"), dict)
        else {}
    )
    response_action = (
        current_payload.get("response_action")
        if isinstance(current_payload.get("response_action"), dict)
        else {}
    )
    current_fingerprint = response_action.get("fingerprint") or confirmation_action.get(
        "fingerprint"
    )

    if request.fingerprint and current_fingerprint and request.fingerprint != current_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Intervention context changed, refresh retrospective before responding",
        )

    if strict_confirm_required and action == "confirm" and not confirmation_action.get("required"):
        return {
            "status": "noop",
            "reason": "confirmation_not_required",
            "retrospective": current_payload,
        }

    if not current_payload.get("display") or not current_payload.get("suggestion"):
        return {
            "status": "noop",
            "reason": "no_active_intervention",
            "retrospective": current_payload,
        }

    if action == "confirm" and confirmation_action.get("confirmed"):
        return {"status": "already_confirmed", "retrospective": current_payload}

    latest = response_action.get("latest") if isinstance(response_action, dict) else None
    if isinstance(latest, dict):
        latest_action = str(latest.get("action", "")).lower()
        latest_fingerprint = latest.get("fingerprint")
        latest_context = str(latest.get("context", "") or "").strip().lower() or None
        if (
            latest_action == action
            and latest_fingerprint == current_fingerprint
            and latest_context == context
        ):
            return {"status": "already_responded", "retrospective": current_payload}

    guardian_role = (
        current_payload.get("guardian_role")
        if isinstance(current_payload.get("guardian_role"), dict)
        else {}
    )
    recovery_step = _guardian_recovery_step(
        action=action,
        context=context,
        suggestion=str(current_payload.get("suggestion", "") or ""),
    )
    base_payload = {
        "days": days,
        "fingerprint": current_fingerprint,
        "suggestion": current_payload.get("suggestion", ""),
        "signals": [
            source.get("signal")
            for source in current_payload.get("suggestion_sources", [])
            if isinstance(source, dict)
        ],
        "note": request.note or "",
        "context": context,
        "representing": guardian_role.get("representing"),
        "facing": guardian_role.get("facing"),
    }
    if recovery_step:
        base_payload["recovery_step"] = recovery_step

    if action == "confirm":
        append_event(
            {
                "type": "guardian_intervention_confirmed",
                "timestamp": datetime.now().isoformat(),
                "payload": base_payload,
            }
        )
    else:
        append_event(
            {
                "type": "guardian_intervention_responded",
                "timestamp": datetime.now().isoformat(),
                "payload": {**base_payload, "action": action},
            }
        )

    updated_payload = build_guardian_retrospective_response(days)
    safe_mode_transition = _maybe_append_safe_mode_transition(
        days=days,
        payload=updated_payload,
        fingerprint=current_fingerprint,
        source_action=action,
    )
    if safe_mode_transition:
        updated_payload = build_guardian_retrospective_response(days)

    status = "confirmed" if action == "confirm" else "responded"
    return {
        "status": status,
        "action": action,
        "recovery_step": recovery_step,
        "safe_mode_transition": safe_mode_transition,
        "retrospective": updated_payload,
    }


@router.post("/retrospective/respond")
async def respond_retrospective_intervention(request: RetrospectiveRespondRequest):
    return _apply_guardian_intervention_response(request, strict_confirm_required=False)


@router.post("/retrospective/confirm")
async def confirm_retrospective_intervention(request: RetrospectiveConfirmRequest):
    return _apply_guardian_intervention_response(
        RetrospectiveRespondRequest(
            days=request.days,
            fingerprint=request.fingerprint,
            action="confirm",
            note=request.note,
            context=request.context,
        ),
        strict_confirm_required=True,
    )


@router.post("/l2/session/start")
async def start_l2_session(request: L2SessionActionRequest):
    session_id = request.session_id or f"l2_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    intention = str(request.intention or "").strip()
    append_event(
        {
            "type": "l2_session_started",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "session_id": session_id,
                "source": "manual",
                "intention": intention,
                "note": request.note or "",
            },
        }
    )
    return {
        "status": "started",
        "session_id": session_id,
        "retrospective": build_guardian_retrospective_response(days=7),
    }


@router.post("/l2/session/resume")
async def resume_l2_session(request: L2SessionActionRequest):
    session_id = request.session_id or _resolve_resumable_l2_session_id()
    if not session_id:
        raise HTTPException(status_code=400, detail="No interrupted L2 session to resume")
    resume_step = str(request.resume_step or "").strip()
    append_event(
        {
            "type": "l2_session_resumed",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "session_id": session_id,
                "source": "manual",
                "resume_step": resume_step,
                "note": request.note or "",
            },
        }
    )
    return {
        "status": "resumed",
        "session_id": session_id,
        "retrospective": build_guardian_retrospective_response(days=7),
    }


@router.post("/l2/session/interrupt")
async def interrupt_l2_session(request: L2SessionActionRequest):
    session_id = request.session_id or _resolve_active_l2_session_id()
    if not session_id:
        raise HTTPException(status_code=400, detail="No active L2 session to interrupt")
    reason = _normalize_l2_interrupt_reason(request.reason)
    append_event(
        {
            "type": "l2_session_interrupted",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "session_id": session_id,
                "reason": reason,
                "source": "manual",
                "note": request.note or "",
            },
        }
    )
    return {
        "status": "interrupted",
        "session_id": session_id,
        "reason": reason,
        "retrospective": build_guardian_retrospective_response(days=7),
    }


@router.post("/l2/session/complete")
async def complete_l2_session(request: L2SessionActionRequest):
    session_id = request.session_id or _resolve_active_l2_session_id()
    if not session_id:
        raise HTTPException(status_code=400, detail="No active L2 session to complete")
    reflection = str(request.reflection or "").strip()
    append_event(
        {
            "type": "l2_session_completed",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "session_id": session_id,
                "source": "manual",
                "reflection": reflection,
                "note": request.note or "",
            },
        }
    )
    return {
        "status": "completed",
        "session_id": session_id,
        "retrospective": build_guardian_retrospective_response(days=7),
    }


@router.get("/guardian/config")
async def get_guardian_config():
    config_payload = _normalized_guardian_config(_load_blueprint_yaml())
    return {
        "source_path": str(BLUEPRINT_CONFIG_PATH),
        "config": config_payload,
    }


@router.put("/guardian/config")
async def update_guardian_config(request: GuardianConfigUpdateRequest):
    intervention_level = (
        request.intervention_level.upper()
        if isinstance(request.intervention_level, str) and request.intervention_level
        else "SOFT"
    )
    if intervention_level not in ALLOWED_INTERVENTION_LEVELS:
        raise HTTPException(
            status_code=400,
            detail="intervention_level must be one of OBSERVE_ONLY | SOFT | ASK",
        )

    high = _coerce_float(request.l2_protection.high, 0.75)
    medium = _coerce_float(request.l2_protection.medium, 0.50)
    if medium > high:
        raise HTTPException(
            status_code=400,
            detail="l2_protection.medium cannot be greater than l2_protection.high",
        )

    current_config = _normalized_guardian_config(_load_blueprint_yaml())
    authority_payload = current_config.get("authority") or _guardian_config_defaults().get(
        "authority", {}
    )
    if not isinstance(authority_payload, dict):
        authority_payload = _guardian_config_defaults().get("authority", {})

    if request.authority is not None:
        escalation = request.authority.escalation
        safe_mode = request.authority.safe_mode
        firm_reminder_resistance = _coerce_int(escalation.firm_reminder_resistance, 2, 1, 99)
        periodic_check_resistance = _coerce_int(escalation.periodic_check_resistance, 4, 1, 99)
        if periodic_check_resistance < firm_reminder_resistance:
            periodic_check_resistance = firm_reminder_resistance

        authority_payload = {
            "escalation": {
                "window_days": _coerce_int(escalation.window_days, 7, 1, 30),
                "firm_reminder_resistance": firm_reminder_resistance,
                "periodic_check_resistance": periodic_check_resistance,
            },
            "safe_mode": {
                "enabled": bool(safe_mode.enabled),
                "resistance_threshold": _coerce_int(
                    safe_mode.resistance_threshold,
                    5,
                    1,
                    999,
                ),
                "min_response_events": _coerce_int(
                    safe_mode.min_response_events,
                    3,
                    1,
                    999,
                ),
                "max_confirmation_ratio": round(
                    _coerce_float(safe_mode.max_confirmation_ratio, 0.34, 0.0, 1.0),
                    2,
                ),
                "recovery_confirmations": _coerce_int(
                    safe_mode.recovery_confirmations,
                    2,
                    1,
                    999,
                ),
                "cooldown_hours": _coerce_int(
                    safe_mode.cooldown_hours,
                    24,
                    1,
                    720,
                ),
            },
        }

    payload = {
        "intervention_level": intervention_level,
        "thresholds": {
            "deviation_signals": {
                "repeated_skip": _coerce_int(request.deviation_signals.repeated_skip, 2),
                "l2_interruption": _coerce_int(request.deviation_signals.l2_interruption, 1),
                "stagnation_days": _coerce_int(request.deviation_signals.stagnation_days, 3),
            },
            "l2_protection": {"high": round(high, 2), "medium": round(medium, 2)},
        },
        "authority": authority_payload,
    }
    _save_guardian_config(payload)
    append_event(
        {
            "type": "guardian_config_updated",
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }
    )
    return {
        "status": "updated",
        "source_path": str(BLUEPRINT_CONFIG_PATH),
        "config": payload,
    }


@router.get("/guardian/autotune/config")
async def get_guardian_autotune_config():
    config_payload = _normalized_guardian_autotune_config(_load_blueprint_yaml())
    return {
        "source_path": str(BLUEPRINT_CONFIG_PATH),
        "config": config_payload,
    }


@router.put("/guardian/autotune/config")
async def update_guardian_autotune_config(request: GuardianAutoTuneConfigUpdateRequest):
    mode = str(request.mode or "shadow").strip().lower()
    if mode not in ALLOWED_GUARDIAN_AUTOTUNE_MODES:
        raise HTTPException(
            status_code=400,
            detail="mode must be 'shadow'",
        )
    payload = {
        "enabled": bool(request.enabled),
        "mode": mode,
        "llm_enabled": bool(request.llm_enabled),
        "trigger": {
            "lookback_days": _coerce_int(request.trigger.lookback_days, 7, 1, 30),
            "min_event_count": _coerce_int(request.trigger.min_event_count, 20, 1, 9999),
            "cooldown_hours": _coerce_int(request.trigger.cooldown_hours, 24, 1, 168),
        },
        "guardrails": {
            "max_int_step": _coerce_int(request.guardrails.max_int_step, 1, 1, 3),
            "max_float_step": round(
                _coerce_float(request.guardrails.max_float_step, 0.05, 0.01, 0.2),
                2,
            ),
            "min_confidence": round(
                _coerce_float(request.guardrails.min_confidence, 0.55, 0.0, 1.0),
                2,
            ),
        },
    }
    _save_guardian_autotune_config(payload)
    append_event(
        {
            "type": "guardian_autotune_config_updated",
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }
    )
    return {
        "status": "updated",
        "source_path": str(BLUEPRINT_CONFIG_PATH),
        "config": payload,
    }


@router.get("/guardian/autotune/shadow/latest")
async def get_guardian_autotune_shadow_latest():
    latest = _load_latest_event("guardian_autotune_shadow_proposed")
    return {
        "config": _normalized_guardian_autotune_config(_load_blueprint_yaml()),
        "latest": latest,
    }


@router.post("/guardian/autotune/shadow/run")
async def run_guardian_autotune_shadow(request: Optional[GuardianAutoTuneRunRequest] = None):
    trigger = request.trigger if isinstance(request, GuardianAutoTuneRunRequest) else "manual"
    return _run_guardian_autotune_shadow(trigger=trigger)


@router.get("/anchor/current")
async def get_anchor_current():
    try:
        anchor = AnchorManager().get_current()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load anchor: {exc}")
    return {
        "blueprint_path": str(BLUEPRINT_PATH),
        "anchor": _anchor_payload(anchor),
    }


@router.get("/anchor/diff")
async def get_anchor_diff():
    if not BLUEPRINT_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Blueprint file not found: {BLUEPRINT_PATH}")

    manager = AnchorManager()
    current = manager.get_current()
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
        diff = manager.diff(current, draft)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate anchor diff: {exc}")

    return {
        "blueprint_path": str(BLUEPRINT_PATH),
        "current": _anchor_payload(current),
        "draft": _anchor_payload(draft),
        "diff": _anchor_diff_payload(diff),
    }


@router.post("/anchor/activate")
async def activate_anchor(request: AnchorActivateRequest):
    if not BLUEPRINT_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Blueprint file not found: {BLUEPRINT_PATH}")

    manager = AnchorManager()
    service = get_goal_service()
    current = manager.get_current()
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
        diff = manager.diff(current, draft)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate anchor draft: {exc}")

    if current and diff.status == "unchanged" and not request.force:
        return {
            "status": "noop",
            "reason": "anchor_unchanged",
            "current": _anchor_payload(current),
            "diff": _anchor_diff_payload(diff),
        }

    try:
        activated = manager.activate(draft)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to activate anchor: {exc}")

    append_event(
        {
            "type": "anchor_activated",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "version": activated.version,
                "source_hash": activated.source_hash,
                "blueprint_path": str(BLUEPRINT_PATH),
            },
        }
    )

    recompute_result = service.recompute_active_alignment(detail_limit=100)
    append_event(
        {
            "type": "goal_alignment_recomputed",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "anchor_version": activated.version,
                **recompute_result,
            },
        }
    )

    return {
        "status": "activated",
        "anchor": _anchor_payload(activated),
        "diff": _anchor_diff_payload(diff),
        "effect": {
            "available": True,
            "anchor_version": activated.version,
            **recompute_result,
        },
    }


@router.get("/anchor/effect")
async def get_anchor_effect():
    latest = _load_latest_event("goal_alignment_recomputed")
    if latest and isinstance(latest.get("payload"), dict):
        payload = dict(latest["payload"])
        payload["available"] = True
        payload["generated_at"] = latest.get("timestamp")
        return payload

    service = get_goal_service()
    current_summary = service.summarize_alignment()
    return {
        "available": False,
        "generated_at": None,
        "anchor_version": None,
        "total_processed": current_summary.get("total_active", 0),
        "affected_count": 0,
        "avg_score_delta": None,
        "before": current_summary,
        "after": current_summary,
        "impacted_goals": [],
    }


@router.get("/visions")
async def list_visions():
    service = get_goal_service()
    return {"visions": [service.node_to_dict(v) for v in service.list_visions()]}


@router.put("/visions/{vision_id}")
async def update_vision(vision_id: str, request: VisionUpdateRequest):
    service = get_goal_service()
    try:
        vision = service.update_vision(
            vision_id,
            title=request.title,
            description=request.description,
        )
    except ValueError as exc:
        message = str(exc).lower()
        if "not found" in message:
            raise HTTPException(status_code=404, detail="Vision not found")
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "vision": service.node_to_dict(vision)}


@router.post("/goals/{goal_id}/confirm")
async def confirm_goal(goal_id: str):
    service = get_goal_service()
    try:
        service.confirm_goal(goal_id, strict_pending=True)
    except ValueError as exc:
        message = str(exc).lower()
        if "not found" in message:
            raise HTTPException(status_code=404, detail="Goal not found")
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "confirmed", "goal_id": goal_id}


@router.post("/goals/{goal_id}/reject")
async def reject_goal(goal_id: str):
    service = get_goal_service()
    try:
        service.reject_goal(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "rejected", "goal_id": goal_id}


@router.post("/goals/{goal_id}/feedback")
async def submit_feedback(goal_id: str, request: FeedbackRequest):
    result = classify_feedback(request.message)
    service = get_goal_service()
    try:
        goal = service.apply_feedback(
            goal_id,
            result.intent.value,
            extracted_reason=result.extracted_reason,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")

    append_event(
        {
            "type": "goal_feedback",
            "goal_id": goal_id,
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "intent": result.intent.value,
                "confidence": result.confidence,
                "message": request.message,
                "progress_percent": result.progress_percent,
            },
        }
    )

    return {
        "status": "success",
        "goal_id": goal_id,
        "detected_intent": result.intent.value,
        "confidence": result.confidence,
        "new_state": goal.state.value,
    }


@router.post("/goals/{goal_id}/action")
async def execute_action(goal_id: str, request: ActionRequest):
    service = get_goal_service()
    action_type = request.action.lower()

    try:
        goal = service.apply_action(goal_id, action_type, reason=request.reason)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")

    append_event(
        {
            "type": "goal_action",
            "goal_id": goal_id,
            "timestamp": datetime.now().isoformat(),
            "payload": {"action": action_type, "reason": request.reason},
        }
    )

    if goal.state == GoalState.COMPLETED:
        append_event(
            {
                "type": "goal_completed",
                "goal_id": goal_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

    return {"status": "success", "goal_id": goal_id, "new_state": goal.state.value}


@router.get("/timeline")
async def get_timeline():
    steward = get_steward()
    registry_goals = [g for g in steward.registry.goals if g.state == GoalState.ACTIVE]

    timeline_items = []
    current_hour = datetime.now().hour
    for idx, goal in enumerate(registry_goals):
        timeline_items.append(
            {
                "id": goal.id,
                "title": goal.title,
                "start": f"{current_hour + idx}:00",
                "end": f"{current_hour + idx + 1}:00",
                "type": "goal",
                "status": "scheduled",
            }
        )
    return {"timeline": timeline_items}


@router.get("/goals")
async def list_goals(state: Optional[str] = None, layer: Optional[str] = None):
    service = get_goal_service()
    all_goals = service.list_nodes(state=state, layer=layer)
    return {
        "goals": [service.node_to_dict(g) for g in all_goals],
        "count": len(all_goals),
    }


@router.get("/events")
async def stream_events():
    async def event_generator():
        if not EVENT_LOG_PATH.exists():
            yield "data: {\"type\": \"system\", \"message\": \"No logs found\"}\n\n"
            return

        with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-10:]:
                yield f"data: {line}\n\n"

            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sys/cycle")
async def trigger_cycle():
    steward = get_steward()
    plan = steward.run_planning_cycle()
    try:
        autotune_result = _run_guardian_autotune_shadow(trigger="cycle")
    except Exception as exc:
        autotune_result = {"status": "error", "mode": "shadow", "reason": str(exc)}
    audit = _normalized_audit(
        raw_audit=plan.get("audit", {}),
        default_strategy="planning_cycle",
        default_trigger="Manual cycle trigger",
        default_constraint="Daily planning bounds",
        default_risk="Over-allocation or stale context",
    )
    return {
        "status": "cycled",
        "generated_actions": plan.get("actions", []),
        "executed_auto_tasks": plan.get("executed_auto_tasks", []),
        "guardian_autotune": autotune_result,
        "audit": audit,
    }


@router.post("/interact")
async def interact(request: InteractionRequest):
    steward = get_steward()
    handler = InteractionHandler(steward.registry, steward.state)
    result = handler.process(request.message)

    if result.action_type == "UPDATE_IDENTITY":
        append_event(
            {
                "type": "identity_updated",
                "timestamp": datetime.now().isoformat(),
                "payload": result.updates,
            }
        )
        create_snapshot(force=True)
    elif result.action_type == "GOAL_FEEDBACK":
        for goal_id, status in result.updates.items():
            append_event(
                {
                    "type": "goal_feedback",
                    "goal_id": goal_id,
                    "timestamp": datetime.now().isoformat(),
                    "payload": {
                        "intent": status,
                        "message": request.message,
                        "source": "nlp_interaction",
                    },
                }
            )

    return {
        "response": result.response_text,
        "action_type": result.action_type,
        "updated_fields": result.updated_fields,
    }
