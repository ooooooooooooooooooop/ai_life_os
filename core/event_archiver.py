"""
Event Archiver - 事件日志归档机制

定期归档旧事件，防止主日志文件无限膨胀。
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple

EVENT_LOG_PATH = Path(__file__).parent.parent / "data" / "event_log.jsonl"
ARCHIVE_DIR = Path(__file__).parent.parent / "data" / "archive"


def _parse_event_timestamp(event: Dict[str, Any]) -> datetime:
    """解析事件时间戳，无效则返回 None。"""
    ts = event.get("timestamp")
    if not ts:
        return None
    try:
        # 处理多种时间格式
        ts_str = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str).replace(tzinfo=None)
    except Exception:
        return None


def _is_valid_event(event: Dict[str, Any]) -> bool:
    """检查事件是否有效（非脏数据）。"""
    ts = _parse_event_timestamp(event)
    if ts is None:
        return False
    # 过滤 1970 年的脏数据
    if ts.year < 2000:
        return False
    return True


def _get_archive_filename(event: Dict[str, Any]) -> str:
    """根据事件时间生成归档文件名。"""
    ts = _parse_event_timestamp(event)
    if ts is None:
        # 无效事件用当前月份
        ts = datetime.now()
    return f"events_{ts.year}-{ts.month:02d}.jsonl"


def archive_old_events(keep_days: int = 90) -> Dict[str, int]:
    """
    归档旧事件。

    Args:
        keep_days: 保留最近多少天的事件

    Returns:
        {"archived": N, "dropped": N, "remaining": N}
    """
    try:
        if not EVENT_LOG_PATH.exists():
            return {"archived": 0, "dropped": 0, "remaining": 0}

        # 读取所有事件
        events = []
        with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        cutoff_date = datetime.now() - timedelta(days=keep_days)

        to_archive: Dict[str, List[Dict[str, Any]]] = {}
        to_keep: List[Dict[str, Any]] = []
        dropped = 0

        for event in events:
            # 过滤无效/脏数据
            if not _is_valid_event(event):
                dropped += 1
                continue

            ts = _parse_event_timestamp(event)

            if ts < cutoff_date:
                # 需要归档
                archive_file = _get_archive_filename(event)
                if archive_file not in to_archive:
                    to_archive[archive_file] = []
                to_archive[archive_file].append(event)
            else:
                # 保留
                to_keep.append(event)

        # 写入归档文件（追加模式）
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archived = 0
        for archive_file, archive_events in to_archive.items():
            archive_path = ARCHIVE_DIR / archive_file
            with open(archive_path, "a", encoding="utf-8") as f:
                for event in archive_events:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
                    archived += 1

        # 重写主文件
        with open(EVENT_LOG_PATH, "w", encoding="utf-8") as f:
            for event in to_keep:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return {
            "archived": archived,
            "dropped": dropped,
            "remaining": len(to_keep),
        }

    except Exception as e:
        print(f"[EventArchiver] 归档失败: {e}")
        return {"archived": 0, "dropped": 0, "remaining": 0}


def get_archive_stats() -> Dict[str, Any]:
    """
    获取归档状态统计。

    Returns:
        {
            "main_file": {"path": str, "lines": int, "size_kb": float},
            "archive_files": [{"path": str, "lines": int, "size_kb": float}, ...]
        }
    """
    result = {
        "main_file": {"path": str(EVENT_LOG_PATH), "lines": 0, "size_kb": 0.0},
        "archive_files": [],
    }

    # 主文件统计
    if EVENT_LOG_PATH.exists():
        with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            result["main_file"]["lines"] = sum(1 for _ in f)
        result["main_file"]["size_kb"] = round(EVENT_LOG_PATH.stat().st_size / 1024, 2)

    # 归档文件统计
    if ARCHIVE_DIR.exists():
        for archive_file in sorted(ARCHIVE_DIR.glob("events_*.jsonl")):
            with open(archive_file, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            size_kb = round(archive_file.stat().st_size / 1024, 2)
            result["archive_files"].append({
                "path": str(archive_file.name),
                "lines": lines,
                "size_kb": size_kb,
            })

    return result


def should_archive() -> bool:
    """
    判断是否需要归档。

    Returns:
        主文件超过 500 条或 300KB 时返回 True
    """
    if not EVENT_LOG_PATH.exists():
        return False

    # 检查行数
    with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
        line_count = sum(1 for _ in f)
    if line_count > 500:
        return True

    # 检查文件大小
    size_kb = EVENT_LOG_PATH.stat().st_size / 1024
    if size_kb > 300:
        return True

    return False
