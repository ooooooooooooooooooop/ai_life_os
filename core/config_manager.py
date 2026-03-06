"""
Configuration manager for AI Life OS.

All tunable runtime constants live here to keep behavior explicit.
Phase 8增强：添加配置验证机制。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.exceptions import ConfigError, ValidationError

CONFIG_DIR = Path(__file__).parent.parent / "config"
RUNTIME_CONFIG_PATH = CONFIG_DIR / "runtime.yaml"


# 配置验证规则
CONFIG_VALIDATION_RULES = {
    "WEEKLY_REVIEW_DAY": {
        "type": int,
        "min": 0,
        "max": 6,
        "description": "周复盘日期（0=周一，6=周日）"
    },
    "DAILY_TASK_LIMIT": {
        "type": int,
        "min": 1,
        "max": 20,
        "description": "每日任务数量限制"
    },
    "EVENT_LOOKBACK": {
        "type": int,
        "min": 10,
        "max": 500,
        "description": "事件回溯数量"
    },
    "MAX_RHYTHM_ACTIONS": {
        "type": int,
        "min": 1,
        "max": 10,
        "description": "最大节奏动作数量"
    },
    "MAX_EXPLORATION_ACTIONS": {
        "type": int,
        "min": 1,
        "max": 10,
        "description": "最大探索动作数量"
    },
    "SNAPSHOT_RETENTION_DAYS": {
        "type": int,
        "min": 1,
        "max": 365,
        "description": "快照保留天数"
    },
    "MIN_TASK_DURATION": {
        "type": int,
        "min": 5,
        "max": 120,
        "description": "最小任务时长（分钟）"
    },
    "RHYTHM_ANALYSIS_TEMPERATURE": {
        "type": float,
        "min": 0.0,
        "max": 1.0,
        "description": "节奏分析温度参数"
    },
    "EXPLORATION_TEMPERATURE": {
        "type": float,
        "min": 0.0,
        "max": 1.0,
        "description": "探索温度参数"
    },
    "MIN_EVENTS_FOR_RHYTHM": {
        "type": int,
        "min": 1,
        "max": 50,
        "description": "节奏分析最小事件数"
    },
    "HABIT_MIN_OCCURRENCES": {
        "type": int,
        "min": 1,
        "max": 20,
        "description": "习惯最小出现次数"
    },
    "HABIT_SUCCESS_RATE_THRESHOLD": {
        "type": float,
        "min": 0.0,
        "max": 1.0,
        "description": "习惯成功率阈值"
    },
    "STATS_MIN_SAMPLE_SIZE": {
        "type": int,
        "min": 1,
        "max": 20,
        "description": "统计最小样本量"
    },
}


def validate_config_value(key: str, value: Any) -> None:
    """
    验证单个配置值。

    Args:
        key: 配置键名
        value: 配置值

    Raises:
        ValidationError: 配置值无效
    """
    if key not in CONFIG_VALIDATION_RULES:
        # 未知配置项，跳过验证
        return

    rules = CONFIG_VALIDATION_RULES[key]
    expected_type = rules["type"]

    # 类型检查
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"配置项 {key} 类型错误：期望 {expected_type.__name__}，实际 {type(value).__name__}",
            field_name=key
        )

    # 范围检查
    if "min" in rules and value < rules["min"]:
        raise ValidationError(
            f"配置项 {key} 值过小：{value} < {rules['min']}",
            field_name=key
        )

    if "max" in rules and value > rules["max"]:
        raise ValidationError(
            f"配置项 {key} 值过大：{value} > {rules['max']}",
            field_name=key
        )


def validate_config_dict(config_dict: Dict[str, Any]) -> List[str]:
    """
    验证配置字典。

    Args:
        config_dict: 配置字典

    Returns:
        验证错误列表（空列表表示验证通过）
    """
    errors = []

    for key, value in config_dict.items():
        try:
            validate_config_value(key, value)
        except ValidationError as e:
            errors.append(str(e))

    return errors


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
    """
    Load runtime overrides from config/runtime.yaml if present.
    
    Phase 8增强：添加配置验证。
    """
    if not RUNTIME_CONFIG_PATH.exists():
        return {}
    try:
        with open(RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}
        
        # 验证配置
        errors = validate_config_dict(config_dict)
        if errors:
            error_msg = "配置验证失败:\n" + "\n".join(errors)
            raise ConfigError(error_msg, config_path=str(RUNTIME_CONFIG_PATH))
        
        return config_dict
    except yaml.YAMLError as e:
        raise ConfigError(
            f"YAML解析错误: {e}",
            config_path=str(RUNTIME_CONFIG_PATH)
        )
    except OSError as e:
        raise ConfigError(
            f"配置文件读取失败: {e}",
            config_path=str(RUNTIME_CONFIG_PATH)
        )


def get_config() -> SystemConfig:
    """
    Build effective config.

    Priority: runtime.yaml overrides > defaults.
    
    Phase 8增强：添加配置验证和错误处理。
    """
    base = SystemConfig()
    
    try:
        overrides = _load_runtime_config()
        for key, value in overrides.items():
            if hasattr(base, key):
                setattr(base, key, value)
    except ConfigError as e:
        # 配置加载失败，使用默认配置并记录警告
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"配置加载失败，使用默认配置: {e}")
    
    return base


config = get_config()
