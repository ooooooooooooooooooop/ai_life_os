"""
Daily Tick Scheduler for AI Life OS.

Handles time progression and system mode checks.
遵循 RIPER Rule 3：通过事件驱动建立显式因果链。

事件类型:
- TimeTick: 日期变更
- ReviewDue: 周期性回顾触发
- MaintenanceDue: 系统维护触发（预留）
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Tuple

import yaml
from pathlib import Path

from core.config_manager import config

CONFIG_DIR = Path(__file__).parent.parent / "config"
SYSTEM_CONFIG_PATH = CONFIG_DIR / "system.yaml"


class EventType(Enum):
    """调度器生成的事件类型。"""
    TIME_TICK = "time_tick"
    REVIEW_DUE = "review_due"
    MAINTENANCE_DUE = "maintenance_due"


def load_system_config() -> Dict[str, Any]:
    """
    Load system configuration.
    On missing file or yaml/safe_load unavailable, returns normal mode.
    """
    if not SYSTEM_CONFIG_PATH.exists():
        return {"current_pause_mode": "normal"}
    try:
        with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as f:
            out = getattr(yaml, "safe_load", None)
            if out is not None:
                return out(f) or {}
    except (AttributeError, ImportError, Exception):
        pass
    return {"current_pause_mode": "normal"}


def get_pause_mode() -> str:
    """
    Get current system pause mode.
    
    Returns:
        One of: 'normal', 'soft_pause', 'hard_pause', 'maintenance'
    """
    sys_config = load_system_config()
    return sys_config.get("current_pause_mode", "normal")


def can_proceed() -> Tuple[bool, str]:
    """
    Check if system can proceed with normal operations.
    
    Returns:
        Tuple of (can_proceed: bool, reason: str)
    """
    mode = get_pause_mode()
    
    if mode == "normal":
        return True, "System running normally"
    elif mode == "soft_pause":
        return False, "Soft pause: new tasks suspended, logging continues"
    elif mode == "hard_pause":
        return False, "Hard pause: all I/O stopped"
    elif mode == "maintenance":
        return False, "Maintenance mode: manual repair only"
    else:
        return True, f"Unknown mode '{mode}', defaulting to normal"


def daily_tick(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    执行每日时间推进并生成相关事件。
    
    Args:
        state: 当前状态字典。
    
    Returns:
        事件列表（可能包含多个事件）。
        - TimeTick: 日期变更时生成
        - ReviewDue: 到达周报日时生成
    
    因果链说明 (RIPER Rule 3):
        触发条件: 日期变更
        成立条件: current_date != today
        失效条件: 已在今日执行过 tick
    """
    events = []
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    
    # Check if already ticked today
    current_date = state.get("time_state", {}).get("current_date", "")
    
    if current_date == today:
        # Already ticked today, no new events
        return events
    
    # Event 1: TimeTick - 日期变更
    events.append({
        "type": EventType.TIME_TICK.value,
        "date": today,
        "previous_date": current_date,
        "timestamp": now.isoformat()
    })
    
    # Event 2: ReviewDue - 周报触发
    # 因果链: weekday == WEEKLY_REVIEW_DAY -> 触发周报
    if now.weekday() == config.WEEKLY_REVIEW_DAY:
        events.append({
            "type": EventType.REVIEW_DUE.value,
            "review_type": "weekly",
            "date": today,
            "trigger_reason": f"Today is weekday {config.WEEKLY_REVIEW_DAY} (configured review day)",
            "timestamp": now.isoformat()
        })
    
    return events


def check_and_tick(state: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    检查暂停模式并执行 tick（如果允许）。
    
    Args:
        state: 当前状态字典。
    
    Returns:
        Tuple of (ticked: bool, events: List[dict])
        - ticked: 是否生成了事件
        - events: 事件列表（用于追加到日志）
    """
    can_run, reason = can_proceed()
    
    if not can_run:
        print(f"[Scheduler] {reason}")
        return False, []
    
    events = daily_tick(state)
    return len(events) > 0, events


def ensure_tick_applied() -> Dict[str, Any]:
    """
    按需推进：若未 tick 则执行 check_and_tick、append 事件并返回更新后状态；否则返回当前状态。
    供 GET /state、POST /sys/cycle 等入口在构造 Steward 前调用。
    """
    from core.snapshot_manager import restore_from_snapshot
    from core.event_sourcing import append_event, rebuild_state
    
    state = restore_from_snapshot()
    ticked, events = check_and_tick(state)
    if events:
        for ev in events:
            append_event(ev)
        return rebuild_state()
    return state
