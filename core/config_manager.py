"""
Configuration manager for AI Life OS.

All tunable runtime constants live here to keep behavior explicit.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"
RUNTIME_CONFIG_PATH = CONFIG_DIR / "runtime.yaml"


@dataclass
class SystemConfig:
    # Scheduling
    WEEKLY_REVIEW_DAY: int = 6

    # Planning limits
    DAILY_TASK_LIMIT: int = 5
    EVENT_LOOKBACK: int = 50
    MAX_RHYTHM_ACTIONS: int = 3
    MAX_EXPLORATION_ACTIONS: int = 2

    # Snapshot retention
    SNAPSHOT_RETENTION_DAYS: int = 30

    # Task granularity
    MIN_TASK_DURATION: int = 25
    RHYTHM_ANALYSIS_TEMPERATURE: float = 0.3
    EXPLORATION_TEMPERATURE: float = 0.7

    # Rhythm analysis thresholds
    MIN_EVENTS_FOR_RHYTHM: int = 5
    DEFAULT_ENERGY_PHASE: str = "leisure"
    DEFAULT_LOG_PATH: str = "notes/learning-log.md"

    # Statistics
    HABIT_MIN_OCCURRENCES: int = 3
    HABIT_SUCCESS_RATE_THRESHOLD: float = 0.6
    STATS_MIN_SAMPLE_SIZE: int = 2

    # Time-of-day phase mapping
    ENERGY_PHASES: dict = None

    def __post_init__(self):
        if self.ENERGY_PHASES is None:
            self.ENERGY_PHASES = {
                "06:00-09:00": "activation",
                "09:00-13:00": "deep_work",
                "13:00-14:00": "connection",
                "14:00-18:00": "logistics",
                "18:00-22:00": "leisure",
            }


def _load_runtime_config() -> dict:
    """Load runtime overrides from config/runtime.yaml if present."""
    if not RUNTIME_CONFIG_PATH.exists():
        return {}
    try:
        with open(RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def get_config() -> SystemConfig:
    """
    Build effective config.

    Priority: runtime.yaml overrides > defaults.
    """
    base = SystemConfig()
    overrides = _load_runtime_config()
    for key, value in overrides.items():
        if hasattr(base, key):
            setattr(base, key, value)
    return base


config = get_config()
