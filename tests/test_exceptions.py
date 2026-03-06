"""
异常处理测试

测试自定义异常的创建和使用。
Phase 8新增测试。
"""

import pytest
from core.exceptions import (
    AILifeError,
    ConfigError,
    StateError,
    InterruptError,
    LLMError,
    LLMConnectionError,
    LLMAuthError,
    LLMTimeoutError,
    LLMRateLimitError,
    EventProcessingError,
    FileOperationError,
    GoalOperationError,
    PerformanceError,
    ValidationError,
)


def test_ai_life_error_basic():
    """测试基础异常类"""
    error = AILifeError("测试错误")

    assert error.message == "测试错误"
    assert error.hint is None
    assert str(error) == "测试错误"


def test_ai_life_error_with_hint():
    """测试带提示的异常"""
    error = AILifeError("测试错误", hint="这是提示")

    assert error.message == "测试错误"
    assert error.hint == "这是提示"
    assert "💡 建议: 这是提示" in error.get_user_message()


def test_config_error():
    """测试配置错误"""
    error = ConfigError("配置文件错误", config_path="/path/to/config.yaml")

    assert error.message == "配置文件错误"
    assert error.config_path == "/path/to/config.yaml"
    assert "请检查配置文件" in error.hint


def test_config_error_without_path():
    """测试无路径的配置错误"""
    error = ConfigError("配置文件错误")

    assert error.message == "配置文件错误"
    assert error.config_path is None
    assert "请检查配置文件格式" in error.hint


def test_state_error():
    """测试状态错误"""
    error = StateError("状态重建失败", corrupted_data="bad_data")

    assert error.message == "状态重建失败"
    assert error.corrupted_data == "bad_data"
    assert "event_log.jsonl" in error.hint


def test_interrupt_error():
    """测试中断错误"""
    error = InterruptError()

    assert error.message == "用户主动中断操作"
    assert error.hint is None


def test_interrupt_error_custom_message():
    """测试自定义消息的中断错误"""
    error = InterruptError("用户取消了操作")

    assert error.message == "用户取消了操作"


def test_llm_error():
    """测试LLM错误"""
    error = LLMError(
        "模型调用失败",
        provider="openai",
        model_name="gpt-4",
        endpoint="https://api.openai.com/v1"
    )

    assert error.provider == "openai"
    assert error.model_name == "gpt-4"
    assert error.endpoint == "https://api.openai.com/v1"
    assert "[openai/gpt-4]" in str(error)


def test_llm_error_user_message():
    """测试LLM错误的用户消息"""
    error = LLMError("调用失败", provider="openai", model_name="gpt-4")

    user_msg = error.get_user_message()
    assert "openai/gpt-4" in user_msg
    assert "调用失败" in user_msg


def test_llm_connection_error():
    """测试LLM连接错误"""
    error = LLMConnectionError(provider="ollama", model_name="llama2")

    assert error.provider == "ollama"
    assert "无法连接到模型服务" in error.message
    assert "ollama serve" in error.hint


def test_llm_connection_error_openai():
    """测试OpenAI连接错误"""
    error = LLMConnectionError(provider="openai", model_name="gpt-4")

    assert "网络连接" in error.hint


def test_llm_auth_error():
    """测试LLM鉴权错误"""
    error = LLMAuthError(provider="openai", model_name="gpt-4")

    assert "鉴权失败" in error.message
    assert "API Key" in error.hint


def test_llm_timeout_error():
    """测试LLM超时错误"""
    error = LLMTimeoutError(
        provider="openai",
        model_name="gpt-4",
        timeout_seconds=30.0
    )

    assert error.timeout_seconds == 30.0
    assert "30.0秒" in error.message
    assert "网络慢" in error.hint


def test_llm_rate_limit_error():
    """测试LLM频率限制错误"""
    error = LLMRateLimitError(
        provider="openai",
        model_name="gpt-4",
        retry_after=60
    )

    assert error.retry_after == 60
    assert "60 秒后重试" in error.hint


def test_llm_rate_limit_error_without_retry():
    """测试无重试时间的频率限制错误"""
    error = LLMRateLimitError(provider="openai", model_name="gpt-4")

    assert error.retry_after is None
    assert "稍后重试" in error.hint


# ========== Phase 8新增异常测试 ==========


def test_event_processing_error():
    """测试事件处理错误"""
    error = EventProcessingError(
        "事件解析失败",
        event_data='{"invalid": json}'
    )

    assert error.message == "事件解析失败"
    assert error.event_data == '{"invalid": json}'
    assert "event_log.jsonl" in error.hint


def test_file_operation_error():
    """测试文件操作错误"""
    error = FileOperationError(
        "文件读取失败",
        file_path="/path/to/file.txt"
    )

    assert error.message == "文件读取失败"
    assert error.file_path == "/path/to/file.txt"
    assert "/path/to/file.txt" in error.hint


def test_file_operation_error_without_path():
    """测试无路径的文件操作错误"""
    error = FileOperationError("文件操作失败")

    assert error.file_path is None
    assert "文件路径和权限" in error.hint


def test_goal_operation_error():
    """测试目标操作错误"""
    error = GoalOperationError(
        "目标创建失败",
        goal_id="goal_123"
    )

    assert error.message == "目标创建失败"
    assert error.goal_id == "goal_123"
    assert "目标操作失败" in error.hint


def test_performance_error():
    """测试性能错误"""
    error = PerformanceError(
        "性能阈值超限",
        metric_name="response_time"
    )

    assert error.message == "性能阈值超限"
    assert error.metric_name == "response_time"
    assert "系统资源" in error.hint


def test_validation_error():
    """测试验证错误"""
    error = ValidationError(
        "数据格式错误",
        field_name="email"
    )

    assert error.message == "数据格式错误"
    assert error.field_name == "email"
    assert "email" in error.hint


def test_validation_error_without_field():
    """测试无字段名的验证错误"""
    error = ValidationError("数据验证失败")

    assert error.field_name is None
    assert "数据格式" in error.hint


def test_exception_inheritance():
    """测试异常继承关系"""
    # 所有自定义异常都应该继承自AILifeError
    assert issubclass(ConfigError, AILifeError)
    assert issubclass(StateError, AILifeError)
    assert issubclass(InterruptError, AILifeError)
    assert issubclass(LLMError, AILifeError)
    assert issubclass(EventProcessingError, AILifeError)
    assert issubclass(FileOperationError, AILifeError)
    assert issubclass(GoalOperationError, AILifeError)
    assert issubclass(PerformanceError, AILifeError)
    assert issubclass(ValidationError, AILifeError)


def test_llm_exception_inheritance():
    """测试LLM异常继承关系"""
    assert issubclass(LLMConnectionError, LLMError)
    assert issubclass(LLMAuthError, LLMError)
    assert issubclass(LLMTimeoutError, LLMError)
    assert issubclass(LLMRateLimitError, LLMError)


def test_exception_can_be_raised():
    """测试异常可以被抛出"""
    with pytest.raises(AILifeError) as exc_info:
        raise ConfigError("测试配置错误")
    
    assert "测试配置错误" in str(exc_info.value)


def test_exception_can_be_caught_by_base_class():
    """测试异常可以被基类捕获"""
    with pytest.raises(AILifeError):
        raise EventProcessingError("事件处理错误")


def test_llm_exception_can_be_caught_by_base():
    """测试LLM异常可以被基类捕获"""
    with pytest.raises(LLMError):
        raise LLMConnectionError(provider="test", model_name="test")


def test_exception_message_formatting():
    """测试异常消息格式化"""
    error = ConfigError("配置缺失", config_path="config.yaml")
    user_msg = error.get_user_message()

    assert "配置缺失" in user_msg
    assert "💡 建议" in user_msg
    assert "config.yaml" in user_msg


def test_multiple_exception_types():
    """测试多种异常类型"""
    errors = [
        ConfigError("配置错误"),
        StateError("状态错误"),
        EventProcessingError("事件错误"),
        FileOperationError("文件错误"),
        GoalOperationError("目标错误"),
        PerformanceError("性能错误"),
        ValidationError("验证错误"),
    ]

    for error in errors:
        assert isinstance(error, AILifeError)
        assert error.message is not None
        assert error.hint is not None or error.hint is None


def test_exception_with_none_values():
    """测试带None值的异常"""
    error = EventProcessingError("错误", event_data=None)
    
    assert error.event_data is None
    assert error.message == "错误"


def test_exception_chaining():
    """测试异常链"""
    try:
        try:
            raise ValueError("原始错误")
        except ValueError as e:
            raise EventProcessingError("事件处理失败") from e
    except EventProcessingError as e:
        assert e.__cause__ is not None
        assert isinstance(e.__cause__, ValueError)
