"""
性能监控模块

提供性能指标记录、统计和导出功能。
Phase 7新增功能。
"""

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, max_history: int = 10000):
        """
        初始化性能监控器。

        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self.metrics: Dict[str, List[float]] = {}
        self.history: List[PerformanceMetric] = []
        self._logger = logging.getLogger(__name__)

    def record(
        self,
        metric_name: str,
        value: float,
        unit: str = "ms",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录性能指标。

        Args:
            metric_name: 指标名称
            value: 指标值
            unit: 单位
            metadata: 元数据
        """
        # 记录到指标字典
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)

        # 记录到历史列表
        metric = PerformanceMetric(
            name=metric_name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        self.history.append(metric)

        # 限制历史记录数量
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        self._logger.debug(f"记录性能指标: {metric_name}={value}{unit}")

    def get_statistics(self, metric_name: str) -> Dict[str, Any]:
        """
        获取指标统计信息。

        Args:
            metric_name: 指标名称

        Returns:
            统计信息字典
        """
        values = self.metrics.get(metric_name, [])

        if not values:
            return {
                "name": metric_name,
                "count": 0,
                "mean": 0,
                "min": 0,
                "max": 0,
                "latest": 0
            }

        return {
            "name": metric_name,
            "count": len(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "latest": values[-1]
        }

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有指标的统计信息。

        Returns:
            所有指标的统计信息
        """
        return {
            name: self.get_statistics(name)
            for name in self.metrics.keys()
        }

    def get_history(
        self,
        metric_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取历史记录。

        Args:
            metric_name: 指标名称，如果为None则返回所有指标
            limit: 返回记录数量限制

        Returns:
            历史记录列表
        """
        if metric_name:
            history = [
                m for m in self.history
                if m.name == metric_name
            ]
        else:
            history = self.history

        # 返回最近的记录
        return [m.to_dict() for m in history[-limit:]]

    def export_metrics(self, output_path: Optional[Path] = None) -> str:
        """
        导出性能指标为JSON格式。

        Args:
            output_path: 输出文件路径，如果为None则返回字符串

        Returns:
            JSON字符串
        """
        data = {
            "metrics": self.get_all_metrics(),
            "history": self.get_history(limit=1000),
            "exported_at": datetime.now().isoformat(),
            "total_records": len(self.history)
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_str, encoding='utf-8')
            self._logger.info(f"性能指标已导出到: {output_path}")

        return json_str

    def clear(self) -> None:
        """清空所有记录"""
        self.metrics.clear()
        self.history.clear()
        self._logger.info("性能监控记录已清空")


# 全局性能监控器实例
_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """
    获取性能监控器单例实例。

    Returns:
        PerformanceMonitor实例
    """
    global _monitor

    if _monitor is None:
        _monitor = PerformanceMonitor()

    return _monitor


def performance_monitor(
    metric_name: str,
    unit: str = "ms",
    metadata: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    性能监控装饰器。

    Args:
        metric_name: 指标名称
        unit: 单位
        metadata: 元数据

    Returns:
        装饰器函数

    Example:
        @performance_monitor("function_execution_time")
        def my_function():
            # 函数逻辑
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (time.time() - start_time) * 1000
                monitor = get_monitor()
                monitor.record(metric_name, duration, unit, metadata)

        return wrapper
    return decorator


@contextmanager
def PerformanceTracker(
    metric_name: str,
    unit: str = "ms",
    metadata: Optional[Dict[str, Any]] = None
):
    """
    性能监控上下文管理器。

    Args:
        metric_name: 指标名称
        unit: 单位
        metadata: 元数据

    Example:
        with PerformanceTracker("database_query_time"):
            # 数据库查询
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = (time.time() - start_time) * 1000
        monitor = get_monitor()
        monitor.record(metric_name, duration, unit, metadata)


# 预定义的性能指标名称
class MetricNames:
    """性能指标名称常量"""
    # Guardian复盘相关
    RETROSPECTIVE_GENERATION_TIME = "retrospective_generation_time"
    SIGNAL_DETECTION_TIME = "signal_detection_time"
    EVENT_RECONSTRUCTION_TIME = "event_reconstruction_time"

    # 文件传感器相关
    FILE_SCAN_TIME = "file_scan_time"
    REALTIME_DETECTION_DELAY = "realtime_detection_delay"
    FILE_CHANGE_PROCESSING_TIME = "file_change_processing_time"

    # 系统性能相关
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    API_RESPONSE_TIME = "api_response_time"


# 便捷函数
def record_metric(
    metric_name: str,
    value: float,
    unit: str = "ms",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    记录性能指标（便捷函数）。

    Args:
        metric_name: 指标名称
        value: 指标值
        unit: 单位
        metadata: 元数据
    """
    get_monitor().record(metric_name, value, unit, metadata)


def get_metric_statistics(metric_name: str) -> Dict[str, Any]:
    """
    获取指标统计信息（便捷函数）。

    Args:
        metric_name: 指标名称

    Returns:
        统计信息字典
    """
    return get_monitor().get_statistics(metric_name)


def export_performance_metrics(output_path: Optional[Path] = None) -> str:
    """
    导出性能指标（便捷函数）。

    Args:
        output_path: 输出文件路径

    Returns:
        JSON字符串
    """
    return get_monitor().export_metrics(output_path)
