"""
文件传感器配置管理模块

提供配置加载、验证和管理功能。
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class WatchPathConfig:
    """监控路径配置"""
    path: str
    enabled: bool = True
    recursive: bool = False
    description: str = ""

    def to_path(self, base_dir: Optional[Path] = None) -> Path:
        """转换为Path对象"""
        if base_dir:
            return base_dir / self.path
        return Path(self.path)


@dataclass
class RealtimeConfig:
    """实时监控配置"""
    enabled: bool = True
    debounce_ms: int = 100
    max_events_per_second: int = 100


@dataclass
class PollingConfig:
    """轮询配置"""
    enabled: bool = True
    interval_seconds: int = 5


@dataclass
class PerformanceConfig:
    """性能配置"""
    max_history_days: int = 7
    max_history_size: int = 10000
    batch_size: int = 100


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file: str = "logs/file_sensor.log"
    max_size_mb: int = 10
    backup_count: int = 5


@dataclass
class FileSensorConfig:
    """文件传感器完整配置"""
    watch_paths: List[WatchPathConfig] = field(default_factory=list)
    realtime: RealtimeConfig = field(default_factory=RealtimeConfig)
    polling: PollingConfig = field(default_factory=PollingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def get_enabled_paths(self, base_dir: Optional[Path] = None) -> List[Path]:
        """获取所有启用的监控路径"""
        return [
            path_config.to_path(base_dir)
            for path_config in self.watch_paths
            if path_config.enabled
        ]


class ConfigLoadError(Exception):
    """配置加载错误"""
    pass


class ConfigValidationError(Exception):
    """配置验证错误"""
    pass


def load_config(config_path: Path) -> FileSensorConfig:
    """
    加载配置文件。

    Args:
        config_path: 配置文件路径

    Returns:
        FileSensorConfig对象

    Raises:
        ConfigLoadError: 配置加载失败
        ConfigValidationError: 配置验证失败
    """
    start_time = time.time()

    try:
        if not config_path.exists():
            raise ConfigLoadError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            raise ConfigLoadError("配置文件为空")

        # 解析监控路径
        watch_paths = []
        for path_data in config_data.get('watch_paths', []):
            watch_paths.append(WatchPathConfig(
                path=path_data.get('path', ''),
                enabled=path_data.get('enabled', True),
                recursive=path_data.get('recursive', False),
                description=path_data.get('description', '')
            ))

        # 解析实时监控配置
        realtime_data = config_data.get('realtime', {})
        realtime = RealtimeConfig(
            enabled=realtime_data.get('enabled', True),
            debounce_ms=realtime_data.get('debounce_ms', 100),
            max_events_per_second=realtime_data.get('max_events_per_second', 100)
        )

        # 解析轮询配置
        polling_data = config_data.get('polling', {})
        polling = PollingConfig(
            enabled=polling_data.get('enabled', True),
            interval_seconds=polling_data.get('interval_seconds', 5)
        )

        # 解析性能配置
        performance_data = config_data.get('performance', {})
        performance = PerformanceConfig(
            max_history_days=performance_data.get('max_history_days', 7),
            max_history_size=performance_data.get('max_history_size', 10000),
            batch_size=performance_data.get('batch_size', 100)
        )

        # 解析日志配置
        logging_data = config_data.get('logging', {})
        logging_config = LoggingConfig(
            level=logging_data.get('level', 'INFO'),
            file=logging_data.get('file', 'logs/file_sensor.log'),
            max_size_mb=logging_data.get('max_size_mb', 10),
            backup_count=logging_data.get('backup_count', 5)
        )

        config = FileSensorConfig(
            watch_paths=watch_paths,
            realtime=realtime,
            polling=polling,
            performance=performance,
            logging=logging_config
        )

        # 验证配置
        validate_config(config)

        load_time = (time.time() - start_time) * 1000
        if load_time > 50:
            print(f"警告: 配置加载时间过长: {load_time:.2f}ms")

        return config

    except yaml.YAMLError as e:
        raise ConfigLoadError(f"YAML解析错误: {e}")
    except Exception as e:
        raise ConfigLoadError(f"配置加载失败: {e}")


def validate_config(config: FileSensorConfig) -> bool:
    """
    验证配置有效性。

    Args:
        config: 配置对象

    Returns:
        验证是否通过

    Raises:
        ConfigValidationError: 配置验证失败
    """
    errors = []

    # 验证监控路径
    if not config.watch_paths:
        errors.append("至少需要一个监控路径")

    for i, path_config in enumerate(config.watch_paths):
        if not path_config.path:
            errors.append(f"监控路径{i+1}不能为空")

    # 验证实时监控配置
    if config.realtime.debounce_ms < 0:
        errors.append("防抖延迟不能为负数")

    if config.realtime.max_events_per_second < 1:
        errors.append("每秒最大事件数必须大于0")

    # 验证轮询配置
    if config.polling.interval_seconds < 1:
        errors.append("轮询间隔必须大于等于1秒")

    # 验证性能配置
    if config.performance.max_history_days < 1:
        errors.append("历史保留天数必须大于等于1天")

    if config.performance.max_history_size < 100:
        errors.append("最大历史记录数必须大于等于100")

    if config.performance.batch_size < 1:
        errors.append("批量处理大小必须大于等于1")

    # 验证日志配置
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config.logging.level not in valid_levels:
        errors.append(f"日志级别必须是: {', '.join(valid_levels)}")

    if errors:
        raise ConfigValidationError("\n".join(errors))

    return True


def get_default_config() -> FileSensorConfig:
    """
    获取默认配置。

    Returns:
        默认配置对象
    """
    return FileSensorConfig(
        watch_paths=[
            WatchPathConfig(path="data/event_log.jsonl", enabled=True, recursive=False),
            WatchPathConfig(path="data/goal_registry.json", enabled=True, recursive=False),
            WatchPathConfig(path="data/snapshots", enabled=True, recursive=True),
        ],
        realtime=RealtimeConfig(enabled=True, debounce_ms=100, max_events_per_second=100),
        polling=PollingConfig(enabled=True, interval_seconds=5),
        performance=PerformanceConfig(max_history_days=7, max_history_size=10000, batch_size=100),
        logging=LoggingConfig(level="INFO", file="logs/file_sensor.log", max_size_mb=10, backup_count=5)
    )


# 全局配置实例
_config: Optional[FileSensorConfig] = None
_config_load_time: Optional[float] = None


def get_config(config_path: Optional[Path] = None, reload: bool = False) -> FileSensorConfig:
    """
    获取配置实例（单例模式）。

    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
        reload: 是否强制重新加载

    Returns:
        配置对象
    """
    global _config, _config_load_time

    if _config is None or reload:
        if config_path is None:
            from core.paths import CONFIG_DIR
            config_path = CONFIG_DIR / "file_sensor.yaml"

        try:
            _config = load_config(config_path)
            _config_load_time = time.time()
        except (ConfigLoadError, ConfigValidationError) as e:
            print(f"警告: 配置加载失败，使用默认配置: {e}")
            _config = get_default_config()
            _config_load_time = time.time()

    return _config


def reload_config(config_path: Optional[Path] = None) -> FileSensorConfig:
    """
    重新加载配置。

    Args:
        config_path: 配置文件路径

    Returns:
        新的配置对象
    """
    return get_config(config_path, reload=True)
