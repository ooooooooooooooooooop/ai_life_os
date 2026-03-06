"""
Threshold Manager Module for Guardian System.

This module contains all threshold management and configuration functions
for the Guardian system, including threshold loading, type coercion,
and blueprint configuration management.

Phase 3 of retrospective.py refactoring.
"""

from pathlib import Path
from typing import Any, Dict, Optional


def _load_blueprint_config() -> Dict[str, Any]:
    """加载blueprint配置，使用缓存机制。"""
    from core.config_cache import load_yaml_with_cache

    config_path = Path(__file__).parent.parent / "config" / "blueprint.yaml"
    return load_yaml_with_cache(config_path)


def _coerce_int(
    value: Any,
    default: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    """Coerce value to int with bounds."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _coerce_float(
    value: Any,
    default: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    """Coerce value to float with bounds."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _coerce_bool(value: Any, default: bool) -> bool:
    """Coerce value to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def get_guardian_thresholds(days: int) -> Dict[str, Any]:
    """
    Get Guardian thresholds with defaults and blueprint overrides.

    Args:
        days: Analysis window in days

    Returns:
        Dictionary of threshold values
    """
    defaults = {
        "repeated_skip": 2,
        "l2_interruption": 1,
        "stagnation_days": 3 if days >= 3 else 1,
        "l2_protection_high": 0.75,
        "l2_protection_medium": 0.50,
        "escalation_window_days": 7,
        "escalation_firm_resistance": 2,
        "escalation_periodic_resistance": 4,
        "safe_mode_enabled": True,
        "safe_mode_resistance_threshold": 5,
        "safe_mode_min_response_events": 3,
        "safe_mode_max_confirmation_ratio": 0.34,
        "safe_mode_recovery_confirmations": 2,
        "safe_mode_cooldown_hours": 24,
        "reminder_budget_window_hours": 6,
        "reminder_budget_max_prompts": 2,
        "reminder_budget_enforce": True,
        "trust_repair_window_hours": 48,
        "trust_repair_negative_streak": 2,
        "cadence_support_recovery_cooldown_hours": 8,
        "cadence_override_cooldown_hours": 3,
        "cadence_observe_cooldown_hours": 12,
        "cadence_trust_repair_cooldown_hours": 12,
    }

    blueprint_config = _load_blueprint_config()
    raw_thresholds = blueprint_config.get("guardian_thresholds", {})
    if not isinstance(raw_thresholds, dict):
        raw_thresholds = {}

    deviation_raw = raw_thresholds.get("deviation_signals", {})
    if not isinstance(deviation_raw, dict):
        deviation_raw = {}

    l2_raw = raw_thresholds.get("l2_protection", {})
    if not isinstance(l2_raw, dict):
        l2_raw = {}

    authority_raw = blueprint_config.get("guardian_authority", {})
    if not isinstance(authority_raw, dict):
        authority_raw = {}

    escalation_raw = authority_raw.get("escalation", {})
    if not isinstance(escalation_raw, dict):
        escalation_raw = {}

    safe_mode_raw = authority_raw.get("safe_mode", {})
    if not isinstance(safe_mode_raw, dict):
        safe_mode_raw = {}
    cadence_raw = authority_raw.get("cadence", {})
    if not isinstance(cadence_raw, dict):
        cadence_raw = {}

    repeated_skip = _coerce_int(
        deviation_raw.get("repeated_skip", raw_thresholds.get("repeated_skip")),
        default=defaults["repeated_skip"],
        min_value=1,
    )
    l2_interruption = _coerce_int(
        deviation_raw.get("l2_interruption", raw_thresholds.get("l2_interruption")),
        default=defaults["l2_interruption"],
        min_value=1,
    )
    stagnation_days = _coerce_int(
        deviation_raw.get("stagnation_days", raw_thresholds.get("stagnation_days")),
        default=defaults["stagnation_days"],
        min_value=1,
    )
    high = _coerce_float(
        l2_raw.get("high", raw_thresholds.get("l2_protection_high")),
        default=defaults["l2_protection_high"],
        min_value=0.0,
        max_value=1.0,
    )
    medium = _coerce_float(
        l2_raw.get("medium", raw_thresholds.get("l2_protection_medium")),
        default=defaults["l2_protection_medium"],
        min_value=0.0,
        max_value=1.0,
    )
    if medium > high:
        medium = high

    escalation_window_days = _coerce_int(
        escalation_raw.get("window_days"),
        default=defaults["escalation_window_days"],
        min_value=1,
        max_value=30,
    )
    escalation_firm_resistance = _coerce_int(
        escalation_raw.get("firm_reminder_resistance"),
        default=defaults["escalation_firm_resistance"],
        min_value=1,
        max_value=99,
    )
    escalation_periodic_resistance = _coerce_int(
        escalation_raw.get("periodic_check_resistance"),
        default=defaults["escalation_periodic_resistance"],
        min_value=1,
        max_value=99,
    )
    if escalation_periodic_resistance < escalation_firm_resistance:
        escalation_periodic_resistance = escalation_firm_resistance

    safe_mode_enabled = _coerce_bool(
        safe_mode_raw.get("enabled"),
        defaults["safe_mode_enabled"],
    )
    safe_mode_resistance_threshold = _coerce_int(
        safe_mode_raw.get("resistance_threshold"),
        default=defaults["safe_mode_resistance_threshold"],
        min_value=1,
        max_value=999,
    )
    safe_mode_min_response_events = _coerce_int(
        safe_mode_raw.get("min_response_events"),
        default=defaults["safe_mode_min_response_events"],
        min_value=1,
        max_value=999,
    )
    safe_mode_max_confirmation_ratio = _coerce_float(
        safe_mode_raw.get("max_confirmation_ratio"),
        default=defaults["safe_mode_max_confirmation_ratio"],
        min_value=0.0,
        max_value=1.0,
    )
    safe_mode_recovery_confirmations = _coerce_int(
        safe_mode_raw.get("recovery_confirmations"),
        default=defaults["safe_mode_recovery_confirmations"],
        min_value=1,
        max_value=999,
    )
    safe_mode_cooldown_hours = _coerce_int(
        safe_mode_raw.get("cooldown_hours"),
        default=defaults["safe_mode_cooldown_hours"],
        min_value=1,
        max_value=720,
    )
    reminder_budget_window_hours = _coerce_int(
        cadence_raw.get("reminder_budget_window_hours"),
        default=defaults["reminder_budget_window_hours"],
        min_value=1,
        max_value=168,
    )
    reminder_budget_max_prompts = _coerce_int(
        cadence_raw.get("reminder_budget_max_prompts"),
        default=defaults["reminder_budget_max_prompts"],
        min_value=1,
        max_value=24,
    )
    reminder_budget_enforce = _coerce_bool(
        cadence_raw.get("reminder_budget_enforce"),
        defaults["reminder_budget_enforce"],
    )
    trust_repair_window_hours = _coerce_int(
        cadence_raw.get("trust_repair_window_hours"),
        default=defaults["trust_repair_window_hours"],
        min_value=1,
        max_value=336,
    )
    trust_repair_negative_streak = _coerce_int(
        cadence_raw.get("trust_repair_negative_streak"),
        default=defaults["trust_repair_negative_streak"],
        min_value=1,
        max_value=20,
    )
    cadence_support_recovery_cooldown_hours = _coerce_int(
        cadence_raw.get("support_recovery_cooldown_hours"),
        default=defaults["cadence_support_recovery_cooldown_hours"],
        min_value=1,
        max_value=168,
    )
    cadence_override_cooldown_hours = _coerce_int(
        cadence_raw.get("override_cooldown_hours"),
        default=defaults["cadence_override_cooldown_hours"],
        min_value=1,
        max_value=168,
    )
    cadence_observe_cooldown_hours = _coerce_int(
        cadence_raw.get("observe_cooldown_hours"),
        default=defaults["cadence_observe_cooldown_hours"],
        min_value=1,
        max_value=168,
    )
    cadence_trust_repair_cooldown_hours = _coerce_int(
        cadence_raw.get("trust_repair_cooldown_hours"),
        default=defaults["cadence_trust_repair_cooldown_hours"],
        min_value=1,
        max_value=168,
    )

    return {
        "repeated_skip": repeated_skip,
        "l2_interruption": l2_interruption,
        "stagnation_days": stagnation_days,
        "l2_protection_high": high,
        "l2_protection_medium": medium,
        "escalation_window_days": escalation_window_days,
        "escalation_firm_resistance": escalation_firm_resistance,
        "escalation_periodic_resistance": escalation_periodic_resistance,
        "safe_mode_enabled": safe_mode_enabled,
        "safe_mode_resistance_threshold": safe_mode_resistance_threshold,
        "safe_mode_min_response_events": safe_mode_min_response_events,
        "safe_mode_max_confirmation_ratio": safe_mode_max_confirmation_ratio,
        "safe_mode_recovery_confirmations": safe_mode_recovery_confirmations,
        "safe_mode_cooldown_hours": safe_mode_cooldown_hours,
        "reminder_budget_window_hours": reminder_budget_window_hours,
        "reminder_budget_max_prompts": reminder_budget_max_prompts,
        "reminder_budget_enforce": reminder_budget_enforce,
        "trust_repair_window_hours": trust_repair_window_hours,
        "trust_repair_negative_streak": trust_repair_negative_streak,
        "cadence_support_recovery_cooldown_hours": cadence_support_recovery_cooldown_hours,
        "cadence_override_cooldown_hours": cadence_override_cooldown_hours,
        "cadence_observe_cooldown_hours": cadence_observe_cooldown_hours,
        "cadence_trust_repair_cooldown_hours": cadence_trust_repair_cooldown_hours,
    }
