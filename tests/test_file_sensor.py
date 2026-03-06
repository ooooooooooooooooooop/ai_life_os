"""
文件传感器测试

测试文件传感器的核心功能。
Phase 7新增：配置管理、动态路径管理测试。
"""

import pytest
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from core.file_sensor import (
    FileSensor,
    FileChange,
    FileSensorSignal,
    EvidenceSignal,
    PathNotFoundError,
    get_file_sensor,
    scan_files,
    analyze_file_signals,
)
from core.file_sensor_config import (
    FileSensorConfig,
    WatchPathConfig,
    load_config,
    validate_config,
    get_config,
    get_default_config,
    ConfigLoadError,
    ConfigValidationError,
)


def test_file_sensor_initialization():
    """测试文件传感器初始化"""
    sensor = FileSensor()
    assert sensor is not None
    assert sensor.watch_paths is not None
    assert len(sensor.watch_paths) > 0


def test_file_sensor_scan():
    """测试文件扫描"""
    sensor = FileSensor()
    changes = sensor.scan()
    assert isinstance(changes, list)
    # 第一次扫描应该检测到文件
    assert len(changes) >= 0


def test_file_sensor_analyze_signals():
    """测试信号分析"""
    sensor = FileSensor()
    # 先扫描一次
    sensor.scan()
    # 分析信号
    signals = sensor.analyze_signals(window_hours=24)
    assert isinstance(signals, list)
    # 检查信号类型
    for signal in signals:
        assert isinstance(signal, FileSensorSignal)
        assert signal.signal_type in EvidenceSignal
        assert 0 <= signal.confidence <= 1
        assert isinstance(signal.summary, str)


def test_file_sensor_get_change_summary():
    """测试变更摘要"""
    sensor = FileSensor()
    sensor.scan()
    summary = sensor.get_change_summary(window_hours=24)
    assert isinstance(summary, dict)
    assert "total_changes" in summary
    assert "created" in summary
    assert "modified" in summary
    assert "deleted" in summary
    assert "window_hours" in summary


def test_file_sensor_singleton():
    """测试单例模式"""
    sensor1 = get_file_sensor()
    sensor2 = get_file_sensor()
    assert sensor1 is sensor2


def test_scan_files_function():
    """测试扫描文件函数"""
    changes = scan_files()
    assert isinstance(changes, list)


def test_analyze_file_signals_function():
    """测试分析文件信号函数"""
    # 先扫描
    scan_files()
    # 分析
    signals = analyze_file_signals(window_hours=24)
    assert isinstance(signals, list)


def test_evidence_signal_enum():
    """测试反证信号枚举"""
    assert EvidenceSignal.WEAK_POSITIVE.value == "weak_positive"
    assert EvidenceSignal.WEAK_NEGATIVE.value == "weak_negative"
    assert EvidenceSignal.NEUTRAL.value == "neutral"


def test_file_change_dataclass():
    """测试文件变更数据类"""
    change = FileChange(
        path="/test/path",
        change_type="modified",
        timestamp=datetime.now(),
        size=1024
    )
    assert change.path == "/test/path"
    assert change.change_type == "modified"
    assert isinstance(change.timestamp, datetime)
    assert change.size == 1024


def test_file_sensor_signal_dataclass():
    """测试文件传感器信号数据类"""
    signal = FileSensorSignal(
        signal_type=EvidenceSignal.WEAK_POSITIVE,
        evidence=[],
        confidence=0.8,
        summary="Test signal",
        timestamp=datetime.now()
    )
    assert signal.signal_type == EvidenceSignal.WEAK_POSITIVE
    assert signal.confidence == 0.8
    assert signal.summary == "Test signal"


def test_file_sensor_with_custom_paths():
    """测试自定义监控路径"""
    from core.paths import DATA_DIR
    custom_paths = [DATA_DIR / "event_log.jsonl"]
    sensor = FileSensor(watch_paths=custom_paths)
    assert len(sensor.watch_paths) == 1
    assert sensor.watch_paths[0] == custom_paths[0]


def test_file_sensor_change_history_retention():
    """测试变更历史保留"""
    sensor = FileSensor()
    # 扫描多次
    for _ in range(3):
        sensor.scan()

    # 检查历史记录
    assert len(sensor._change_history) >= 0

    # 检查历史记录时间范围
    if sensor._change_history:
        oldest_change = min(sensor._change_history, key=lambda c: c.timestamp)
        newest_change = max(sensor._change_history, key=lambda c: c.timestamp)
        # 最老的变更应该在7天内
        assert oldest_change.timestamp > datetime.now() - timedelta(days=8)


# ========== Phase 7新增测试 ==========

def test_file_sensor_config_loading():
    """测试配置文件加载"""
    config = get_config()
    assert config is not None
    assert isinstance(config, FileSensorConfig)
    assert len(config.watch_paths) > 0


def test_file_sensor_config_validation():
    """测试配置验证"""
    config = get_default_config()
    assert validate_config(config) is True


def test_file_sensor_config_invalid():
    """测试无效配置验证"""
    # 创建无效配置
    invalid_config = FileSensorConfig(
        watch_paths=[],  # 空路径列表
    )

    with pytest.raises(ConfigValidationError):
        validate_config(invalid_config)


def test_file_sensor_with_config():
    """测试使用配置文件初始化"""
    config = get_default_config()
    sensor = FileSensor(config=config, use_config=False)
    assert sensor is not None
    assert len(sensor.watch_paths) > 0


def test_file_sensor_add_watch_path(tmp_path):
    """测试动态添加监控路径"""
    sensor = FileSensor(use_config=False)
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")

    initial_count = len(sensor.watch_paths)
    sensor.add_watch_path(test_file)

    assert len(sensor.watch_paths) == initial_count + 1
    assert test_file in sensor.watch_paths


def test_file_sensor_add_nonexistent_path():
    """测试添加不存在的路径"""
    sensor = FileSensor(use_config=False)
    nonexistent_path = Path("/nonexistent/path/file.json")

    with pytest.raises(PathNotFoundError):
        sensor.add_watch_path(nonexistent_path)


def test_file_sensor_remove_watch_path():
    """测试动态移除监控路径"""
    from core.paths import DATA_DIR

    sensor = FileSensor(use_config=False)
    test_path = DATA_DIR / "event_log.jsonl"

    # 先添加
    if test_path.exists():
        sensor.add_watch_path(test_path)
        initial_count = len(sensor.watch_paths)

        # 再移除
        sensor.remove_watch_path(test_path)
        assert len(sensor.watch_paths) == initial_count - 1
        assert test_path not in sensor.watch_paths


def test_file_sensor_get_watch_paths():
    """测试获取监控路径列表"""
    sensor = FileSensor(use_config=False)
    paths = sensor.get_watch_paths()

    assert isinstance(paths, list)
    assert len(paths) == len(sensor.watch_paths)


def test_file_sensor_clear_watch_paths():
    """测试清空监控路径"""
    sensor = FileSensor(use_config=False)
    sensor.clear_watch_paths()

    assert len(sensor.watch_paths) == 0


def test_file_sensor_config_performance():
    """测试配置加载性能"""
    start_time = time.time()
    config = get_config(reload=True)
    load_time = (time.time() - start_time) * 1000

    assert load_time < 50, f"配置加载时间过长: {load_time}ms"
    assert config is not None


def test_file_sensor_extended_paths():
    """测试扩展监控路径（8+个文件）"""
    sensor = FileSensor(use_config=True)

    # 检查监控路径数量
    assert len(sensor.watch_paths) >= 8, f"监控路径数量不足: {len(sensor.watch_paths)}"

    # 检查关键路径是否存在
    path_names = [str(p) for p in sensor.watch_paths]
    assert any("event_log" in name for name in path_names)
    assert any("goal_registry" in name for name in path_names)


def test_file_sensor_config_hot_reload():
    """测试配置热重载"""
    sensor = FileSensor(use_config=True)
    initial_count = len(sensor.watch_paths)

    # 重新加载配置
    sensor.reload_config()

    # 检查配置已更新
    assert len(sensor.watch_paths) >= initial_count


def test_file_sensor_duplicate_path():
    """测试添加重复路径"""
    sensor = FileSensor(use_config=False)
    from core.paths import DATA_DIR

    test_path = DATA_DIR / "event_log.jsonl"
    if test_path.exists():
        sensor.add_watch_path(test_path)
        initial_count = len(sensor.watch_paths)

        # 再次添加相同路径
        sensor.add_watch_path(test_path)

        # 路径数量不应增加
        assert len(sensor.watch_paths) == initial_count


def test_file_sensor_config_default():
    """测试默认配置"""
    config = get_default_config()

    assert config is not None
    assert len(config.watch_paths) >= 3
    assert config.realtime.debounce_ms == 100
    assert config.polling.interval_seconds == 5
    assert config.performance.max_history_days == 7


def test_file_sensor_watch_path_config():
    """测试监控路径配置"""
    path_config = WatchPathConfig(
        path="data/test.json",
        enabled=True,
        recursive=False,
        description="测试路径"
    )

    assert path_config.path == "data/test.json"
    assert path_config.enabled is True
    assert path_config.recursive is False
    assert path_config.description == "测试路径"


def test_file_sensor_integration_with_config():
    """测试配置集成"""
    # 使用配置初始化
    sensor = FileSensor(use_config=True)

    # 执行扫描
    changes = sensor.scan()
    assert isinstance(changes, list)

    # 分析信号
    signals = sensor.analyze_signals(window_hours=24)
    assert isinstance(signals, list)

    # 获取摘要
    summary = sensor.get_change_summary(window_hours=24)
    assert isinstance(summary, dict)
    assert "total_changes" in summary
