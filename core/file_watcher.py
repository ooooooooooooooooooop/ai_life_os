"""
实时文件监控模块

使用watchdog库实现跨平台实时文件监控。
Phase 7新增功能。
"""

import logging
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Event
from typing import Callable, Dict, List, Optional

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from core.file_sensor import FileChange


class Debouncer:
    """防抖器，避免频繁触发事件"""

    def __init__(self, wait_ms: int = 100):
        """
        初始化防抖器。

        Args:
            wait_ms: 防抖等待时间（毫秒）
        """
        self.wait_ms = wait_ms
        self._last_event_time: Dict[str, float] = {}
        self._logger = logging.getLogger(__name__)

    def should_process(self, key: str) -> bool:
        """
        判断是否应该处理事件。

        Args:
            key: 事件键（通常是文件路径）

        Returns:
            是否应该处理
        """
        current_time = time.time()
        last_time = self._last_event_time.get(key, 0)

        if current_time - last_time < self.wait_ms / 1000:
            self._logger.debug(f"防抖过滤: {key}")
            return False

        self._last_event_time[key] = current_time
        return True

    def clear(self) -> None:
        """清空防抖记录"""
        self._last_event_time.clear()


class FileEventHandler(FileSystemEventHandler):
    """文件系统事件处理器"""

    def __init__(
        self,
        event_queue: Queue,
        debounce_ms: int = 100,
        max_events_per_second: int = 100
    ):
        """
        初始化事件处理器。

        Args:
            event_queue: 事件队列
            debounce_ms: 防抖延迟（毫秒）
            max_events_per_second: 每秒最大事件数
        """
        super().__init__()
        self.event_queue = event_queue
        self.debouncer = Debouncer(debounce_ms)
        self.max_events_per_second = max_events_per_second
        self._event_count: Dict[str, int] = defaultdict(int)
        self._last_reset_time = time.time()
        self._logger = logging.getLogger(__name__)

    def _check_rate_limit(self, path: str) -> bool:
        """检查是否超过速率限制"""
        current_time = time.time()

        # 每秒重置计数器
        if current_time - self._last_reset_time >= 1.0:
            self._event_count.clear()
            self._last_reset_time = current_time

        # 检查是否超过限制
        if self._event_count[path] >= self.max_events_per_second:
            self._logger.warning(f"事件速率超限: {path}")
            return False

        self._event_count[path] += 1
        return True

    def on_modified(self, event: FileSystemEvent) -> None:
        """文件修改事件"""
        if event.is_directory:
            return

        path = event.src_path

        # 防抖检查
        if not self.debouncer.should_process(path):
            return

        # 速率限制检查
        if not self._check_rate_limit(path):
            return

        self._logger.debug(f"检测到文件修改: {path}")

        change = FileChange(
            path=path,
            change_type='modified',
            timestamp=datetime.now()
        )
        self.event_queue.put(change)

    def on_created(self, event: FileSystemEvent) -> None:
        """文件创建事件"""
        if event.is_directory:
            return

        path = event.src_path

        # 防抖检查
        if not self.debouncer.should_process(path):
            return

        # 速率限制检查
        if not self._check_rate_limit(path):
            return

        self._logger.debug(f"检测到文件创建: {path}")

        change = FileChange(
            path=path,
            change_type='created',
            timestamp=datetime.now()
        )
        self.event_queue.put(change)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """文件删除事件"""
        if event.is_directory:
            return

        path = event.src_path

        # 防抖检查
        if not self.debouncer.should_process(path):
            return

        # 速率限制检查
        if not self._check_rate_limit(path):
            return

        self._logger.debug(f"检测到文件删除: {path}")

        change = FileChange(
            path=path,
            change_type='deleted',
            timestamp=datetime.now()
        )
        self.event_queue.put(change)


class RealtimeFileWatcher:
    """实时文件监控器"""

    def __init__(
        self,
        debounce_ms: int = 100,
        max_events_per_second: int = 100
    ):
        """
        初始化实时文件监控器。

        Args:
            debounce_ms: 防抖延迟（毫秒）
            max_events_per_second: 每秒最大事件数
        """
        self.debounce_ms = debounce_ms
        self.max_events_per_second = max_events_per_second

        self.event_queue: Queue = Queue()
        self._observer: Optional[Observer] = None
        self._handler: Optional[FileEventHandler] = None
        self._watch_handles: Dict[str, any] = {}
        self._stop_event = Event()
        self._logger = logging.getLogger(__name__)

    def add_path(self, path: Path, recursive: bool = False) -> None:
        """
        添加监控路径。

        Args:
            path: 监控路径
            recursive: 是否递归监控
        """
        if not path.exists():
            self._logger.warning(f"路径不存在，无法监控: {path}")
            return

        if self._observer is None:
            self._logger.warning("监控器未启动，无法添加路径")
            return

        path_str = str(path)

        if path_str in self._watch_handles:
            self._logger.debug(f"路径已在监控中: {path}")
            return

        try:
            # 如果是文件，监控其父目录
            watch_path = path.parent if path.is_file() else path

            handle = self._observer.schedule(
                self._handler,
                str(watch_path),
                recursive=recursive
            )

            self._watch_handles[path_str] = handle
            self._logger.info(f"添加监控路径: {path} (递归: {recursive})")

        except Exception as e:
            self._logger.error(f"添加监控路径失败: {path}, 错误: {e}")

    def remove_path(self, path: Path) -> None:
        """
        移除监控路径。

        Args:
            path: 要移除的路径
        """
        path_str = str(path)

        if path_str not in self._watch_handles:
            self._logger.debug(f"路径不在监控中: {path}")
            return

        try:
            handle = self._watch_handles[path_str]
            self._observer.unschedule(handle)
            del self._watch_handles[path_str]
            self._logger.info(f"移除监控路径: {path}")

        except Exception as e:
            self._logger.error(f"移除监控路径失败: {path}, 错误: {e}")

    def start(self) -> None:
        """启动实时监控"""
        if self._observer is not None:
            self._logger.warning("监控器已启动")
            return

        try:
            self._handler = FileEventHandler(
                self.event_queue,
                self.debounce_ms,
                self.max_events_per_second
            )

            self._observer = Observer()
            self._observer.start()
            self._stop_event.clear()

            self._logger.info("实时文件监控器已启动")

        except Exception as e:
            self._logger.error(f"启动监控器失败: {e}")
            raise

    def stop(self) -> None:
        """停止实时监控"""
        if self._observer is None:
            self._logger.warning("监控器未启动")
            return

        try:
            self._stop_event.set()
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None
            self._handler = None
            self._watch_handles.clear()

            self._logger.info("实时文件监控器已停止")

        except Exception as e:
            self._logger.error(f"停止监控器失败: {e}")

    def get_changes(self, timeout_ms: int = 100) -> List[FileChange]:
        """
        获取文件变更。

        Args:
            timeout_ms: 超时时间（毫秒）

        Returns:
            文件变更列表
        """
        changes = []

        try:
            while True:
                change = self.event_queue.get(timeout=timeout_ms / 1000)
                changes.append(change)
        except Empty:
            pass

        return changes

    def is_running(self) -> bool:
        """检查监控器是否正在运行"""
        return self._observer is not None and self._observer.is_alive()


class FallbackManager:
    """回退管理器，处理实时监控失败时的回退"""

    def __init__(self):
        """初始化回退管理器"""
        self._current_mode = "realtime"
        self._logger = logging.getLogger(__name__)

    def execute_with_fallback(
        self,
        primary: Callable,
        fallback: Callable,
        error_msg: str = "实时监控失败"
    ) -> any:
        """
        执行操作，失败时回退。

        Args:
            primary: 主要操作
            fallback: 回退操作
            error_msg: 错误消息

        Returns:
            操作结果
        """
        try:
            return primary()
        except Exception as e:
            self._logger.warning(f"{error_msg}: {e}，回退到轮询模式")
            self._current_mode = "polling"
            return fallback()

    def get_current_mode(self) -> str:
        """获取当前模式"""
        return self._current_mode

    def set_mode(self, mode: str) -> None:
        """
        设置模式。

        Args:
            mode: 模式名称（realtime或polling）
        """
        if mode in ["realtime", "polling"]:
            self._current_mode = mode
            self._logger.info(f"切换到{mode}模式")
        else:
            self._logger.warning(f"未知模式: {mode}")


# 全局实时监控器实例
_realtime_watcher: Optional[RealtimeFileWatcher] = None


def get_realtime_watcher(
    debounce_ms: int = 100,
    max_events_per_second: int = 100
) -> RealtimeFileWatcher:
    """
    获取实时监控器单例实例。

    Args:
        debounce_ms: 防抖延迟（毫秒）
        max_events_per_second: 每秒最大事件数

    Returns:
        RealtimeFileWatcher实例
    """
    global _realtime_watcher

    if _realtime_watcher is None:
        _realtime_watcher = RealtimeFileWatcher(
            debounce_ms,
            max_events_per_second
        )

    return _realtime_watcher
