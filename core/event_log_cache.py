"""
事件日志缓存模块

提供事件日志的内存缓存机制，减少重复I/O操作，提升性能。
Phase 8新增功能。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from core.paths import DATA_DIR


class EventLogCache:
    """事件日志缓存器

    基于文件修改时间（mtime）实现缓存失效机制，
    提供增量加载功能，只加载新增事件。
    """

    def __init__(self, log_path: Optional[Path] = None):
        """
        初始化事件日志缓存器。

        Args:
            log_path: 事件日志文件路径，默认为data/event_log.jsonl
        """
        self.log_path = log_path or DATA_DIR / "event_log.jsonl"
        self._cache: List[Dict[str, Any]] = []
        self._last_mtime: Optional[float] = None
        self._last_size: int = 0
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)

    def _should_reload(self) -> bool:
        """
        检查是否需要重新加载日志文件。

        Returns:
            是否需要重新加载
        """
        if not self.log_path.exists():
            return False

        try:
            stat = self.log_path.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size

            # 如果文件修改时间或大小变化，需要重新加载
            if self._last_mtime is None or self._last_size == 0:
                return True

            if current_mtime != self._last_mtime or current_size != self._last_size:
                return True

            return False

        except Exception as e:
            self._logger.error(f"检查日志文件状态失败: {e}")
            return False

    def _load_full(self) -> List[Dict[str, Any]]:
        """
        完整加载事件日志。

        Returns:
            事件列表
        """
        events = []

        if not self.log_path.exists():
            return events

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError as e:
                        self._logger.warning(
                            f"事件日志第{line_num}行JSON解析失败: {e}"
                        )
                        continue

            # 更新缓存状态
            stat = self.log_path.stat()
            self._last_mtime = stat.st_mtime
            self._last_size = stat.st_size

            self._logger.info(
                f"完整加载事件日志: {len(events)}个事件, "
                f"文件大小: {self._last_size}字节"
            )

            return events

        except Exception as e:
            self._logger.error(f"加载事件日志失败: {e}")
            return events

    def _load_incremental(self) -> List[Dict[str, Any]]:
        """
        增量加载新增事件。

        Returns:
            新增事件列表
        """
        if not self.log_path.exists():
            return []

        new_events = []

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                # 跳过已加载的事件
                for _ in range(len(self._cache)):
                    f.readline()

                # 读取新增事件
                for line_num, line in enumerate(f, len(self._cache) + 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        new_events.append(event)
                    except json.JSONDecodeError as e:
                        self._logger.warning(
                            f"事件日志第{line_num}行JSON解析失败: {e}"
                        )
                        continue

            # 更新缓存状态
            stat = self.log_path.stat()
            self._last_mtime = stat.st_mtime
            self._last_size = stat.st_size

            if new_events:
                self._logger.info(f"增量加载事件日志: {len(new_events)}个新事件")

            return new_events

        except Exception as e:
            self._logger.error(f"增量加载事件日志失败: {e}")
            return []

    def get_events(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        获取事件列表。

        Args:
            force_reload: 是否强制重新加载

        Returns:
            事件列表
        """
        with self._lock:
            # 如果缓存为空或需要重新加载
            if not self._cache or force_reload or self._should_reload():
                # 如果缓存不为空且文件修改了，尝试增量加载
                if self._cache and not force_reload:
                    new_events = self._load_incremental()
                    self._cache.extend(new_events)
                else:
                    # 否则完整加载
                    self._cache = self._load_full()

            return self._cache.copy()

    def get_events_since(
        self,
        since: datetime,
        force_reload: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取指定时间之后的事件。

        Args:
            since: 起始时间
            force_reload: 是否强制重新加载

        Returns:
            事件列表
        """
        events = self.get_events(force_reload)

        filtered_events = []
        for event in events:
            timestamp_str = event.get("timestamp", "")
            if timestamp_str:
                try:
                    # 尝试解析时间戳
                    event_time = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                    if event_time.replace(tzinfo=None) >= since:
                        filtered_events.append(event)
                except (ValueError, AttributeError):
                    # 如果时间戳解析失败，包含该事件
                    filtered_events.append(event)

        return filtered_events

    def get_events_for_period(
        self,
        days: int = 7,
        force_reload: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取指定天数内的事件。

        Args:
            days: 天数
            force_reload: 是否强制重新加载

        Returns:
            事件列表
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        return self.get_events_since(cutoff_date, force_reload)

    def clear_cache(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._last_mtime = None
            self._last_size = 0
            self._logger.info("事件日志缓存已清空")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息。

        Returns:
            缓存统计信息
        """
        with self._lock:
            return {
                "cached_events": len(self._cache),
                "last_mtime": self._last_mtime,
                "last_size": self._last_size,
                "log_path": str(self.log_path),
                "log_exists": self.log_path.exists(),
            }


# 全局事件日志缓存实例
_event_log_cache: Optional[EventLogCache] = None
_cache_lock = Lock()


def get_event_log_cache(log_path: Optional[Path] = None) -> EventLogCache:
    """
    获取事件日志缓存单例实例。

    Args:
        log_path: 事件日志文件路径

    Returns:
        EventLogCache实例
    """
    global _event_log_cache

    with _cache_lock:
        if _event_log_cache is None:
            _event_log_cache = EventLogCache(log_path)

        return _event_log_cache


def load_events(days: int = 7, force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    加载事件日志（便捷函数）。

    Args:
        days: 加载最近N天的事件
        force_reload: 是否强制重新加载

    Returns:
        事件列表
    """
    cache = get_event_log_cache()
    return cache.get_events_for_period(days, force_reload)


def load_all_events(force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    加载所有事件日志（便捷函数）。

    Args:
        force_reload: 是否强制重新加载

    Returns:
        事件列表
    """
    cache = get_event_log_cache()
    return cache.get_events(force_reload)


def clear_event_log_cache() -> None:
    """清空事件日志缓存（便捷函数）"""
    cache = get_event_log_cache()
    cache.clear_cache()


def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息（便捷函数）。

    Returns:
        缓存统计信息
    """
    cache = get_event_log_cache()
    return cache.get_cache_stats()
