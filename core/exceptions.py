"""
AI Life OS 异常定义模块。

定义系统中所有自定义异常的层次结构：
- AILifeError: 基类，所有已知错误
- ConfigError: 配置文件错误
- StateError: 状态相关错误
- InterruptError: 用户主动中断
- LLMError: 模型调用相关错误
"""
from typing import Optional


class AILifeError(Exception):
    """AI Life OS 基础异常类。

    所有系统内已知错误都继承自此类。
    捕获此类可以处理所有预期的错误情况。
    """

    def __init__(self, message: str, hint: Optional[str] = None):
        """
        Args:
            message: 错误描述
            hint: 对用户的操作建议
        """
        super().__init__(message)
        self.message = message
        self.hint = hint

    def get_user_message(self) -> str:
        """返回用户友好的错误消息。"""
        if self.hint:
            return f"{self.message}\n💡 建议: {self.hint}"
        return self.message


class ConfigError(AILifeError):
    """配置文件错误。

    当配置文件缺失、格式错误或内容非法时抛出。
    """

    def __init__(self, message: str, config_path: Optional[str] = None):
        hint = f"请检查配置文件: {config_path}" if config_path else "请检查配置文件格式"
        super().__init__(message, hint)
        self.config_path = config_path


class StateError(AILifeError):
    """状态相关错误。

    当状态重建失败或事件数据格式错误时抛出。
    """

    def __init__(self, message: str, corrupted_data: Optional[str] = None):
        hint = "状态可能已损坏，建议检查 event_log.jsonl"
        super().__init__(message, hint)
        self.corrupted_data = corrupted_data


class InterruptError(AILifeError):
    """用户主动中断。

    当用户主动终止操作（非 Crash）时抛出。
    这是预期行为，不应视为错误。
    """

    def __init__(self, message: str = "用户主动中断操作"):
        super().__init__(message, hint=None)


class LLMError(AILifeError):
    """LLM 调用相关错误的基类。

    当模型调用失败时抛出，包含调用上下文信息。
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        self.provider = provider or "unknown"
        self.model_name = model_name or "unknown"
        self.endpoint = endpoint

        context = f"[{self.provider}/{self.model_name}]"
        full_message = f"{context} {message}"

        super().__init__(full_message)

    def get_user_message(self) -> str:
        """返回包含模型信息的用户友好消息。"""
        base = f"模型调用失败 ({self.provider}/{self.model_name}): {self.message}"
        if self.hint:
            return f"{base}\n💡 建议: {self.hint}"
        return base


class LLMConnectionError(LLMError):
    """无法连接到 LLM 服务。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        message = "无法连接到模型服务"
        super().__init__(message, provider, model_name, endpoint)

        if provider == "ollama":
            self.hint = "请确保 Ollama 正在运行 (ollama serve)"
        elif provider == "openai":
            self.hint = "请检查网络连接或 API 端点配置"
        else:
            self.hint = "请检查模型服务是否正在运行"


class LLMAuthError(LLMError):
    """LLM 鉴权失败。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        message = "模型鉴权失败"
        super().__init__(message, provider, model_name, endpoint)
        self.hint = "请检查 API Key 是否正确配置"


class LLMTimeoutError(LLMError):
    """LLM 调用超时。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        message = "模型调用超时"
        if timeout_seconds:
            message = f"模型调用超时 ({timeout_seconds}秒)"
        super().__init__(message, provider, model_name, endpoint)
        self.timeout_seconds = timeout_seconds
        self.hint = "可能是网络慢或模型响应时间长，请稍后重试"


class LLMRateLimitError(LLMError):
    """LLM 请求频率限制。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        message = "请求频率超限"
        super().__init__(message, provider, model_name, endpoint)
        self.retry_after = retry_after
        if retry_after:
            self.hint = f"请在 {retry_after} 秒后重试"
        else:
            self.hint = "请稍后重试"


# ========== Phase 8新增异常类型 ==========


class EventProcessingError(AILifeError):
    """事件处理错误。

    当事件解析、验证或处理失败时抛出。
    """

    def __init__(self, message: str, event_data: Optional[str] = None):
        hint = "事件数据可能已损坏，建议检查 event_log.jsonl"
        super().__init__(message, hint)
        self.event_data = event_data


class FileOperationError(AILifeError):
    """文件操作错误。

    当文件读取、写入或操作失败时抛出。
    """

    def __init__(self, message: str, file_path: Optional[str] = None):
        hint = f"请检查文件: {file_path}" if file_path else "请检查文件路径和权限"
        super().__init__(message, hint)
        self.file_path = file_path


class GoalOperationError(AILifeError):
    """目标操作错误。

    当目标创建、更新或删除失败时抛出。
    """

    def __init__(self, message: str, goal_id: Optional[str] = None):
        hint = "目标操作失败，请检查目标数据"
        super().__init__(message, hint)
        self.goal_id = goal_id


class PerformanceError(AILifeError):
    """性能相关错误。

    当性能监控或性能阈值超限时抛出。
    """

    def __init__(self, message: str, metric_name: Optional[str] = None):
        hint = "性能问题，请检查系统资源"
        super().__init__(message, hint)
        self.metric_name = metric_name


class ValidationError(AILifeError):
    """数据验证错误。

    当数据验证失败时抛出。
    """

    def __init__(self, message: str, field_name: Optional[str] = None):
        hint = f"请检查字段: {field_name}" if field_name else "请检查数据格式"
        super().__init__(message, hint)
        self.field_name = field_name
