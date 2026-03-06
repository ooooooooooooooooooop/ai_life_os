"""
性能监控测试

测试性能监控模块的核心功能。
Phase 8新增测试。
"""

import json
import time
from pathlib import Path
from core.performance_monitor import (
    PerformanceMonitor,
    PerformanceMetric,
    performance_monitor,
    PerformanceTracker,
    get_monitor,
    record_metric,
    get_metric_statistics,
    export_performance_metrics,
    MetricNames,
)


def test_performance_monitor_initialization():
    """测试性能监控器初始化"""
    monitor = PerformanceMonitor()
    assert monitor is not None
    assert monitor.metrics == {}
    assert monitor.history == []


def test_performance_monitor_record():
    """测试性能指标记录"""
    monitor = PerformanceMonitor()
    monitor.record("test_metric", 10.5, "ms")

    assert "test_metric" in monitor.metrics
    assert len(monitor.metrics["test_metric"]) == 1
    assert monitor.metrics["test_metric"][0] == 10.5


def test_performance_monitor_record_multiple():
    """测试多次记录性能指标"""
    monitor = PerformanceMonitor()
    
    for i in range(5):
        monitor.record("test_metric", i * 10.0, "ms")

    assert len(monitor.metrics["test_metric"]) == 5
    assert monitor.metrics["test_metric"] == [0.0, 10.0, 20.0, 30.0, 40.0]


def test_performance_monitor_get_statistics():
    """测试获取统计信息"""
    monitor = PerformanceMonitor()
    
    # 记录多个值
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    for value in values:
        monitor.record("test_metric", value, "ms")

    stats = monitor.get_statistics("test_metric")

    assert stats["count"] == 5
    assert stats["mean"] == 30.0
    assert stats["min"] == 10.0
    assert stats["max"] == 50.0
    assert stats["latest"] == 50.0


def test_performance_monitor_get_statistics_empty():
    """测试获取空指标的统计信息"""
    monitor = PerformanceMonitor()
    stats = monitor.get_statistics("nonexistent_metric")

    assert stats["count"] == 0
    assert stats["mean"] == 0
    assert stats["min"] == 0
    assert stats["max"] == 0


def test_performance_monitor_get_all_metrics():
    """测试获取所有指标"""
    monitor = PerformanceMonitor()
    
    monitor.record("metric1", 10.0, "ms")
    monitor.record("metric2", 20.0, "ms")
    monitor.record("metric3", 30.0, "ms")

    all_metrics = monitor.get_all_metrics()

    assert len(all_metrics) == 3
    assert "metric1" in all_metrics
    assert "metric2" in all_metrics
    assert "metric3" in all_metrics


def test_performance_monitor_get_history():
    """测试获取历史记录"""
    monitor = PerformanceMonitor()
    
    monitor.record("metric1", 10.0, "ms")
    monitor.record("metric2", 20.0, "ms")

    history = monitor.get_history()

    assert len(history) == 2
    assert history[0]["name"] == "metric1"
    assert history[0]["value"] == 10.0
    assert history[1]["name"] == "metric2"
    assert history[1]["value"] == 20.0


def test_performance_monitor_get_history_with_filter():
    """测试过滤历史记录"""
    monitor = PerformanceMonitor()
    
    monitor.record("metric1", 10.0, "ms")
    monitor.record("metric2", 20.0, "ms")
    monitor.record("metric1", 30.0, "ms")

    history = monitor.get_history(metric_name="metric1")

    assert len(history) == 2
    assert all(h["name"] == "metric1" for h in history)


def test_performance_monitor_export_metrics():
    """测试导出性能指标"""
    monitor = PerformanceMonitor()
    
    monitor.record("metric1", 10.0, "ms")
    monitor.record("metric2", 20.0, "ms")

    json_str = monitor.export_metrics()

    # 验证JSON格式
    data = json.loads(json_str)
    assert "metrics" in data
    assert "history" in data
    assert "exported_at" in data
    assert "total_records" in data
    assert data["total_records"] == 2


def test_performance_monitor_export_to_file(tmp_path):
    """测试导出性能指标到文件"""
    monitor = PerformanceMonitor()
    
    monitor.record("metric1", 10.0, "ms")
    monitor.record("metric2", 20.0, "ms")

    output_file = tmp_path / "performance.json"
    json_str = monitor.export_metrics(output_file)

    # 验证文件已创建
    assert output_file.exists()

    # 验证文件内容
    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert "metrics" in data
    assert data["total_records"] == 2


def test_performance_monitor_clear():
    """测试清空监控记录"""
    monitor = PerformanceMonitor()
    
    monitor.record("metric1", 10.0, "ms")
    monitor.record("metric2", 20.0, "ms")

    assert len(monitor.metrics) == 2
    assert len(monitor.history) == 2

    monitor.clear()

    assert len(monitor.metrics) == 0
    assert len(monitor.history) == 0


def test_performance_monitor_max_history():
    """测试历史记录限制"""
    monitor = PerformanceMonitor(max_history=5)
    
    # 记录超过限制的值
    for i in range(10):
        monitor.record("test_metric", i, "ms")

    # 历史记录应该被限制
    assert len(monitor.history) == 5
    # 应该保留最新的记录
    assert monitor.history[-1].value == 9


def test_performance_monitor_decorator():
    """测试性能监控装饰器"""
    monitor = PerformanceMonitor()

    @performance_monitor("test_function")
    def test_function():
        time.sleep(0.01)  # 10ms
        return "result"

    # 使用装饰器
    result = test_function()

    assert result == "result"
    # 注意：装饰器使用全局monitor，这里只验证功能正常


def test_performance_tracker_context_manager():
    """测试性能监控上下文管理器"""
    monitor = PerformanceMonitor()

    with PerformanceTracker("test_operation"):
        time.sleep(0.01)  # 10ms

    # 注意：上下文管理器使用全局monitor，这里只验证功能正常


def test_get_monitor_singleton():
    """测试获取监控器单例"""
    monitor1 = get_monitor()
    monitor2 = get_monitor()

    assert monitor1 is monitor2


def test_record_metric_function():
    """测试记录指标便捷函数"""
    # 记录指标
    record_metric("test_metric", 100.0, "ms")

    # 获取统计信息
    stats = get_metric_statistics("test_metric")

    assert stats["count"] >= 1
    assert stats["latest"] == 100.0


def test_metric_names_constants():
    """测试性能指标名称常量"""
    assert MetricNames.RETROSPECTIVE_GENERATION_TIME == "retrospective_generation_time"
    assert MetricNames.FILE_SCAN_TIME == "file_scan_time"
    assert MetricNames.MEMORY_USAGE == "memory_usage"
    assert MetricNames.CPU_USAGE == "cpu_usage"


def test_performance_metric_dataclass():
    """测试性能指标数据类"""
    from datetime import datetime

    metric = PerformanceMetric(
        name="test_metric",
        value=10.5,
        unit="ms",
        timestamp=datetime.now(),
        metadata={"key": "value"}
    )

    assert metric.name == "test_metric"
    assert metric.value == 10.5
    assert metric.unit == "ms"
    assert isinstance(metric.timestamp, datetime)
    assert metric.metadata == {"key": "value"}


def test_performance_metric_to_dict():
    """测试性能指标转换为字典"""
    from datetime import datetime

    metric = PerformanceMetric(
        name="test_metric",
        value=10.5,
        unit="ms",
        timestamp=datetime.now()
    )

    metric_dict = metric.to_dict()

    assert metric_dict["name"] == "test_metric"
    assert metric_dict["value"] == 10.5
    assert metric_dict["unit"] == "ms"
    assert "timestamp" in metric_dict


def test_performance_monitor_with_metadata():
    """测试带元数据的性能记录"""
    monitor = PerformanceMonitor()
    
    monitor.record(
        "test_metric",
        10.0,
        "ms",
        metadata={"operation": "test", "user": "test_user"}
    )

    # 验证历史记录包含元数据
    history = monitor.get_history()
    assert len(history) == 1
    assert history[0]["metadata"]["operation"] == "test"
    assert history[0]["metadata"]["user"] == "test_user"


def test_performance_monitor_multiple_metrics():
    """测试多个指标的统计"""
    monitor = PerformanceMonitor()
    
    # 记录多个指标
    for i in range(5):
        monitor.record("metric_a", i * 10.0, "ms")
        monitor.record("metric_b", i * 20.0, "ms")

    # 获取所有指标
    all_metrics = monitor.get_all_metrics()

    assert len(all_metrics) == 2
    assert all_metrics["metric_a"]["mean"] == 20.0
    assert all_metrics["metric_b"]["mean"] == 40.0


def test_export_performance_metrics_function(tmp_path):
    """测试导出性能指标便捷函数"""
    # 记录一些指标
    record_metric("test_metric", 50.0, "ms")

    # 导出到文件
    output_file = tmp_path / "performance_export.json"
    json_str = export_performance_metrics(output_file)

    # 验证文件已创建
    assert output_file.exists()

    # 验证JSON格式
    data = json.loads(json_str)
    assert "metrics" in data
    assert "exported_at" in data
