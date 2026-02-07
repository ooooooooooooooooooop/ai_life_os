"""
Snapshot Manager for AI Life OS.

Manages state snapshots for faster loading and recovery.
Supports incremental snapshots and automatic cleanup.
"""
import dataclasses
import json
import os
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.event_sourcing import (
    DATA_DIR,
    EVENT_LOG_PATH,
    STATE_SNAPSHOT_PATH,
    rebuild_state,
    get_initial_state
)


# 快照目录
SNAPSHOT_DIR = DATA_DIR / "snapshots"

# 默认配置（经验值，可根据实际情况调整）
DEFAULT_SNAPSHOT_INTERVAL = 50  # 每 50 条事件创建检查点
DEFAULT_RETENTION_DAYS = 30  # 保留 30 天的历史快照


def ensure_snapshot_dir() -> None:
    """Ensure the snapshot directory exists."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def get_event_count() -> int:
    """Get the current number of events in the log."""
    if not EVENT_LOG_PATH.exists():
        return 0
    
    count = 0
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def get_latest_snapshot_event_count() -> int:
    """Get the event count from the latest snapshot metadata."""
    ensure_snapshot_dir()
    
    snapshots = list(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snapshots:
        return 0
    
    # 获取最新快照
    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    
    try:
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("_meta", {}).get("event_count", 0)
    except (json.JSONDecodeError, IOError):
        return 0


def should_create_snapshot(interval: int = DEFAULT_SNAPSHOT_INTERVAL) -> bool:
    """
    Check if a new snapshot should be created.
    
    Args:
        interval: Number of events between snapshots (经验值)
    
    Returns:
        True if new snapshot is needed.
    """
    current_count = get_event_count()
    last_snapshot_count = get_latest_snapshot_event_count()
    
    return (current_count - last_snapshot_count) >= interval


def create_snapshot(force: bool = False) -> Optional[Path]:
    """
    Create a new state snapshot.
    
    Args:
        force: If True, create snapshot regardless of interval.
    
    Returns:
        Path to the created snapshot, or None if not created.
    """
    if not force and not should_create_snapshot():
        return None
    
    ensure_snapshot_dir()
    
    # 重建当前状态
    state = rebuild_state()
    event_count = get_event_count()
    
    # 添加元数据
    state["_meta"] = {
        "created_at": datetime.now().isoformat(),
        "event_count": event_count,
        "version": "1.0"
    }
    
    def _json_default(o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"snapshot_{timestamp}.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=_json_default)
    state_copy = {k: v for k, v in state.items() if k != "_meta"}
    with open(STATE_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(state_copy, f, ensure_ascii=False, indent=2, default=_json_default)
    
    return snapshot_path


def load_latest_snapshot() -> Optional[Dict[str, Any]]:
    """
    Load the most recent snapshot.
    
    Returns:
        State dictionary or None if no snapshot exists.
    """
    ensure_snapshot_dir()
    
    snapshots = list(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snapshots:
        # 尝试加载主快照文件
        if STATE_SNAPSHOT_PATH.exists():
            with open(STATE_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    # 获取最新快照
    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    
    try:
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 移除元数据
            data.pop("_meta", None)
            return data
    except (json.JSONDecodeError, IOError):
        return None


def list_snapshots() -> List[Dict[str, Any]]:
    """
    List all available snapshots with metadata.
    
    Returns:
        List of snapshot info dictionaries.
    """
    ensure_snapshot_dir()
    
    snapshots = []
    for path in SNAPSHOT_DIR.glob("snapshot_*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                meta = data.get("_meta", {})
                snapshots.append({
                    "path": str(path),
                    "filename": path.name,
                    "created_at": meta.get("created_at"),
                    "event_count": meta.get("event_count"),
                    "size_bytes": path.stat().st_size
                })
        except (json.JSONDecodeError, IOError):
            continue
    
    # 按创建时间排序（最新在前）
    snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return snapshots


def cleanup_old_snapshots(retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """
    Remove snapshots older than retention period.
    
    Args:
        retention_days: Number of days to retain snapshots (经验值)
    
    Returns:
        Number of snapshots removed.
    """
    ensure_snapshot_dir()
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    removed = 0
    
    for path in SNAPSHOT_DIR.glob("snapshot_*.json"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if mtime < cutoff_date:
                path.unlink()
                removed += 1
        except (OSError, IOError):
            continue
    
    return removed


def restore_from_snapshot(snapshot_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Restore state from a specific snapshot.
    
    Args:
        snapshot_path: Path to snapshot file. If None, uses latest.
    
    Returns:
        Restored state dictionary.
    """
    if snapshot_path:
        path = Path(snapshot_path)
        if not path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
            state.pop("_meta", None)
            return state
    else:
        state = load_latest_snapshot()
        if state is None:
            return get_initial_state()
        return state
