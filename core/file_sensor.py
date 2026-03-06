"""
文件传感器模块

监控文件变更，检测用户行为模式，为Guardian提供反证信号。
Phase 7增强：支持动态路径管理、配置文件加载、扩展监控范围。
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from core.file_sensor_config import (
    FileSensorConfig,
    WatchPathConfig,
    get_config,
    ConfigLoadError,
    ConfigValidationError
)


class EvidenceSignal(Enum):
    """反证信号类型"""
    WEAK_POSITIVE = "weak_positive"  # 可能完成（有进展迹象）
    WEAK_NEGATIVE = "weak_negative"  # 可能在逃避（伪努力）
    NEUTRAL = "neutral"              # 无明显信号


@dataclass
class FileChange:
    """文件变更记录"""
    path: str
    change_type: str  # 'created', 'modified', 'deleted'
    timestamp: datetime
    size: Optional[int] = None


@dataclass
class FileSensorSignal:
    """文件传感器信号"""
    signal_type: EvidenceSignal
    evidence: List[FileChange]
    confidence: float
    summary: str
    timestamp: datetime


class PathNotFoundError(Exception):
    """路径不存在错误"""
    pass


class FileSensor:
    """文件传感器，监控文件变更并生成反证信号

    Phase 7增强功能：
    - 支持动态添加/移除监控路径
    - 支持配置文件加载
    - 扩展监控范围至8+个文件
    """

    def __init__(
        self,
        watch_paths: Optional[List[Path]] = None,
        config: Optional[FileSensorConfig] = None,
        use_config: bool = True
    ):
        """
        初始化文件传感器。

        Args:
            watch_paths: 要监控的路径列表，如果为None则使用配置文件或默认路径
            config: 配置对象，如果为None则自动加载
            use_config: 是否使用配置文件
        """
        self._logger = logging.getLogger(__name__)

        # 加载配置
        self._config = config
        if use_config and config is None:
            try:
                self._config = get_config()
            except Exception as e:
                self._logger.warning(f"配置加载失败，使用默认配置: {e}")
                self._config = None

        # 初始化监控路径
        if watch_paths is not None:
            self.watch_paths = watch_paths
        elif self._config is not None:
            from core.paths import PROJECT_ROOT
            self.watch_paths = self._config.get_enabled_paths(PROJECT_ROOT)
        else:
            self.watch_paths = self._get_default_watch_paths()

        self._file_states: Dict[str, Dict[str, Any]] = {}
        self._change_history: List[FileChange] = []
        self._last_scan_time: Optional[datetime] = None

        # 实时监控相关（Phase 7新增）
        self._realtime_watcher = None
        self._use_realtime = False

        self._logger.info(f"文件传感器初始化完成，监控{len(self.watch_paths)}个路径")

    def _get_default_watch_paths(self) -> List[Path]:
        """获取默认监控路径"""
        from core.paths import DATA_DIR

        return [
            DATA_DIR / "event_log.jsonl",
            DATA_DIR / "goal_registry.json",
            DATA_DIR / "snapshots",
        ]

    def scan(self) -> List[FileChange]:
        """
        扫描文件变更。

        如果启用了实时监控，则从实时监控器获取变更；
        否则使用轮询模式扫描文件。

        Returns:
            检测到的文件变更列表
        """
        # 如果启用了实时监控，使用实时模式
        if self._use_realtime and self._realtime_watcher:
            return self.get_realtime_changes()

        # 否则使用轮询模式
        return self._poll_scan()

    def _poll_scan(self) -> List[FileChange]:
        """
        轮询模式扫描文件变更。

        Returns:
            检测到的文件变更列表
        """
        from core.performance_monitor import PerformanceTracker, MetricNames

        with PerformanceTracker(MetricNames.FILE_SCAN_TIME):
            changes = []
            current_time = datetime.now()

            for watch_path in self.watch_paths:
                if not watch_path.exists():
                    continue

                if watch_path.is_file():
                    file_changes = self._scan_file(watch_path, current_time)
                    changes.extend(file_changes)
                elif watch_path.is_dir():
                    file_changes = self._scan_directory(watch_path, current_time)
                    changes.extend(file_changes)

            self._change_history.extend(changes)
            self._last_scan_time = current_time

            # 保留最近7天的变更历史（或配置的天数）
            max_days = 7
            if self._config:
                max_days = self._config.performance.max_history_days

            cutoff_time = current_time - timedelta(days=max_days)
            self._change_history = [
                change for change in self._change_history
                if change.timestamp > cutoff_time
            ]

            return changes

    def _scan_file(self, file_path: Path, current_time: datetime) -> List[FileChange]:
        """扫描单个文件"""
        changes = []
        path_str = str(file_path)

        try:
            stat = file_path.stat()
            current_mtime = datetime.fromtimestamp(stat.st_mtime)
            current_size = stat.st_size

            if path_str in self._file_states:
                old_state = self._file_states[path_str]
                if current_mtime > old_state['mtime']:
                    changes.append(FileChange(
                        path=path_str,
                        change_type='modified',
                        timestamp=current_time,
                        size=current_size
                    ))
            else:
                changes.append(FileChange(
                    path=path_str,
                    change_type='created',
                    timestamp=current_time,
                    size=current_size
                ))

            self._file_states[path_str] = {
                'mtime': current_mtime,
                'size': current_size
            }
        except Exception:
            pass

        return changes

    def _scan_directory(self, dir_path: Path, current_time: datetime) -> List[FileChange]:
        """扫描目录"""
        changes = []

        try:
            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    file_changes = self._scan_file(file_path, current_time)
                    changes.extend(file_changes)
        except Exception:
            pass

        return changes

    def analyze_signals(self, window_hours: int = 24) -> List[FileSensorSignal]:
        """
        分析文件变更，生成反证信号。

        Args:
            window_hours: 分析时间窗口（小时）

        Returns:
            反证信号列表
        """
        signals = []
        current_time = datetime.now()
        window_start = current_time - timedelta(hours=window_hours)

        # 获取时间窗口内的变更
        recent_changes = [
            change for change in self._change_history
            if change.timestamp > window_start
        ]

        if not recent_changes:
            return signals

        # 分析事件日志变更
        event_log_changes = [
            change for change in recent_changes
            if 'event_log' in change.path
        ]

        if event_log_changes:
            # 事件日志有变更，可能是积极行为
            signals.append(FileSensorSignal(
                signal_type=EvidenceSignal.WEAK_POSITIVE,
                evidence=event_log_changes,
                confidence=0.6,
                summary=f"事件日志在{window_hours}小时内有{len(event_log_changes)}次变更",
                timestamp=current_time
            ))

        # 分析目标注册表变更
        goal_registry_changes = [
            change for change in recent_changes
            if 'goal_registry' in change.path
        ]

        if goal_registry_changes:
            # 目标注册表有变更，可能是积极行为
            signals.append(FileSensorSignal(
                signal_type=EvidenceSignal.WEAK_POSITIVE,
                evidence=goal_registry_changes,
                confidence=0.7,
                summary=f"目标注册表在{window_hours}小时内有{len(goal_registry_changes)}次变更",
                timestamp=current_time
            ))

        # 分析快照变更
        snapshot_changes = [
            change for change in recent_changes
            if 'snapshot' in change.path
        ]

        if snapshot_changes:
            # 快照有变更，可能是系统活动
            signals.append(FileSensorSignal(
                signal_type=EvidenceSignal.WEAK_POSITIVE,
                evidence=snapshot_changes,
                confidence=0.5,
                summary=f"快照在{window_hours}小时内有{len(snapshot_changes)}次变更",
                timestamp=current_time
            ))

        # 如果没有任何变更，可能是消极行为
        if not signals and window_hours >= 24:
            signals.append(FileSensorSignal(
                signal_type=EvidenceSignal.WEAK_NEGATIVE,
                evidence=[],
                confidence=0.4,
                summary=f"在{window_hours}小时内未检测到任何文件变更",
                timestamp=current_time
            ))

        return signals

    def get_change_summary(self, window_hours: int = 24) -> Dict[str, Any]:
        """
        获取文件变更摘要。

        Args:
            window_hours: 分析时间窗口（小时）

        Returns:
            变更摘要
        """
        current_time = datetime.now()
        window_start = current_time - timedelta(hours=window_hours)

        recent_changes = [
            change for change in self._change_history
            if change.timestamp > window_start
        ]

        return {
            "total_changes": len(recent_changes),
            "created": len([c for c in recent_changes if c.change_type == 'created']),
            "modified": len([c for c in recent_changes if c.change_type == 'modified']),
            "deleted": len([c for c in recent_changes if c.change_type == 'deleted']),
            "window_hours": window_hours,
            "last_scan_time": self._last_scan_time.isoformat() if self._last_scan_time else None,
        }

    # ========== Phase 7新增功能：动态路径管理 ==========

    def add_watch_path(self, path: Path) -> None:
        """
        动态添加监控路径。

        Args:
            path: 要添加的路径

        Raises:
            PathNotFoundError: 路径不存在
        """
        if not path.exists():
            raise PathNotFoundError(f"路径不存在: {path}")

        if path not in self.watch_paths:
            self.watch_paths.append(path)
            self._logger.info(f"添加监控路径: {path}")

            # 如果实时监控已启动，添加到监控器
            if self._realtime_watcher:
                self._realtime_watcher.add_path(path)

    def remove_watch_path(self, path: Path) -> None:
        """
        动态移除监控路径。

        Args:
            path: 要移除的路径
        """
        if path in self.watch_paths:
            self.watch_paths.remove(path)
            self._logger.info(f"移除监控路径: {path}")

            # 如果实时监控已启动，从监控器移除
            if self._realtime_watcher:
                self._realtime_watcher.remove_path(path)

            # 清理该路径的文件状态
            path_str = str(path)
            if path_str in self._file_states:
                del self._file_states[path_str]

    def get_watch_paths(self) -> List[Path]:
        """
        获取当前所有监控路径。

        Returns:
            监控路径列表
        """
        return self.watch_paths.copy()

    def clear_watch_paths(self) -> None:
        """清空所有监控路径"""
        self.watch_paths.clear()
        self._file_states.clear()
        self._logger.info("已清空所有监控路径")

    def reload_config(self) -> None:
        """
        重新加载配置文件并更新监控路径。

        注意：这会替换所有现有的监控路径。
        """
        try:
            from core.file_sensor_config import reload_config
            from core.paths import PROJECT_ROOT

            self._config = reload_config()
            self.watch_paths = self._config.get_enabled_paths(PROJECT_ROOT)
            self._file_states.clear()
            self._logger.info(f"配置重新加载完成，监控{len(self.watch_paths)}个路径")

        except Exception as e:
            self._logger.error(f"配置重新加载失败: {e}")
            raise

    # ========== Phase 7新增功能：实时监控 ==========

    def enable_realtime_monitoring(self) -> None:
        """启用实时监控"""
        if self._realtime_watcher is None:
            from core.file_watcher import RealtimeFileWatcher

            debounce_ms = 100
            max_events = 100

            if self._config:
                debounce_ms = self._config.realtime.debounce_ms
                max_events = self._config.realtime.max_events_per_second

            self._realtime_watcher = RealtimeFileWatcher(
                debounce_ms=debounce_ms,
                max_events_per_second=max_events
            )

        # 添加所有监控路径
        for path in self.watch_paths:
            recursive = False
            if self._config:
                for path_config in self._config.watch_paths:
                    if str(path).endswith(path_config.path):
                        recursive = path_config.recursive
                        break

            self._realtime_watcher.add_path(path, recursive=recursive)

        # 启动监控器
        self._realtime_watcher.start()
        self._use_realtime = True

        self._logger.info("实时监控已启用")

    def disable_realtime_monitoring(self) -> None:
        """禁用实时监控"""
        if self._realtime_watcher:
            self._realtime_watcher.stop()
            self._realtime_watcher = None

        self._use_realtime = False
        self._logger.info("实时监控已禁用")

    def is_realtime_enabled(self) -> bool:
        """检查实时监控是否启用"""
        return self._use_realtime and self._realtime_watcher is not None

    def get_realtime_changes(self, timeout_ms: int = 100) -> List[FileChange]:
        """
        获取实时文件变更。

        Args:
            timeout_ms: 超时时间（毫秒）

        Returns:
            文件变更列表
        """
        if not self.is_realtime_enabled():
            return []

        changes = self._realtime_watcher.get_changes(timeout_ms)
        self._change_history.extend(changes)

        return changes


# 全局文件传感器实例
_file_sensor: Optional[FileSensor] = None


def get_file_sensor() -> FileSensor:
    """获取文件传感器单例实例"""
    global _file_sensor
    if _file_sensor is None:
        _file_sensor = FileSensor()
    return _file_sensor


def scan_files() -> List[FileChange]:
    """扫描文件变更"""
    return get_file_sensor().scan()


def analyze_file_signals(window_hours: int = 24) -> List[FileSensorSignal]:
    """分析文件信号"""
    return get_file_sensor().analyze_signals(window_hours)
