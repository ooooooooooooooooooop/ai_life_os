"""
Intervention Tracker - 干预抵抗计数持久化

持久化存储干预抵抗计数，支持系统重启后恢复状态。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

STATE_FILE = Path(__file__).parent.parent / "data" / "intervention_state.json"


def _load_state() -> Dict[str, Any]:
    """加载干预状态文件。"""
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    """保存干预状态到文件。"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _compute_level(resistance_count: int) -> str:
    """根据抵抗计数计算干预级别。"""
    if resistance_count >= 3:
        return "periodic_check"
    elif resistance_count >= 1:
        return "firm_reminder"
    else:
        return "gentle_nudge"


def record_resistance(key: str) -> None:
    """
    记录一次抵抗，自动升级干预级别，写回文件。

    Args:
        key: 目标 ID 或信号类型
    """
    state = _load_state()

    if key not in state:
        state[key] = {
            "resistance_count": 0,
            "level": "gentle_nudge",
            "last_updated": datetime.now().isoformat(),
        }

    state[key]["resistance_count"] += 1
    state[key]["level"] = _compute_level(state[key]["resistance_count"])
    state[key]["last_updated"] = datetime.now().isoformat()

    _save_state(state)


def record_acceptance(key: str) -> None:
    """
    记录用户响应，计数归零，级别重置，写回文件。

    Args:
        key: 目标 ID 或信号类型
    """
    state = _load_state()

    state[key] = {
        "resistance_count": 0,
        "level": "gentle_nudge",
        "last_updated": datetime.now().isoformat(),
    }

    _save_state(state)


def get_intervention_level(key: str) -> str:
    """
    读取当前干预级别。

    Args:
        key: 目标 ID 或信号类型

    Returns:
        干预级别: "gentle_nudge" | "firm_reminder" | "periodic_check"
    """
    state = _load_state()

    if key not in state:
        return "gentle_nudge"

    return state[key].get("level", "gentle_nudge")
