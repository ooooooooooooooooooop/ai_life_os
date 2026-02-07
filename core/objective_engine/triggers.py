"""
TriggerEngine: time-based and cooldown-based trigger checks.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class TriggerType(Enum):
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"


@dataclass
class TriggerContext:
    trigger_type: TriggerType
    trigger_source: str
    timestamp: str
    cooldown_key: str


class TriggerEngine:
    def __init__(self, config: Any):
        self._config = config
        self._cooldowns: Dict[str, bool] = {}

    def should_trigger(self, ctx: TriggerContext) -> bool:
        return not self._cooldowns.get(ctx.cooldown_key, False)

    def set_cooldown(self, key: str) -> None:
        self._cooldowns[key] = True
