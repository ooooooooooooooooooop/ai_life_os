"""
Failure Handling Strategies for AI Life OS.

遵循 RIPER Rule 3：建立显式因果链，区分不同失败类型的处理逻辑。

失败类型分类:
- UserReject: 用户主观不想做 → 降低偏好权重
- ContextMismatch: 客观条件不满足 → 保留权重，增加前置检查
- ResourceShortage: 时间/精力不足 → 重新调度
- SystemError: 系统/规划错误 → 移除并记录
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class FailureType(Enum):
    """失败类型枚举。"""
    USER_REJECT = "user_reject"      # 用户主动跳过（不想做）
    CONTEXT_MISMATCH = "context_mismatch"  # 客观条件不满足（做不了）
    RESOURCE_SHORTAGE = "resource_shortage"  # 时间/精力不足
    SYSTEM_ERROR = "system_error"    # 系统或规划错误
    UNKNOWN = "unknown"


@dataclass
class FailureContext:
    """失败上下文信息。"""
    task_id: str
    failure_type: FailureType
    reason: str
    original_task: Dict[str, Any]

    # 可选：历史失败次数（用于升级策略）
    failure_count: int = 1


@dataclass
class HandlingResult:
    """
    处理结果。

    因果链说明:
        action: 采取的动作
        rationale: 为什么采取此动作（因果链）
        confidence: 策略置信度（0-1）
    """
    task_id: str
    action: str
    rationale: str
    confidence: float = 0.8
    metadata: Optional[Dict[str, Any]] = None


class FailureStrategy(ABC):
    """失败处理策略基类。"""

    @abstractmethod
    def can_handle(self, context: FailureContext) -> bool:
        """判断此策略是否适用于给定的失败类型。"""
        pass

    @abstractmethod
    def handle(self, context: FailureContext) -> HandlingResult:
        """执行处理逻辑。"""
        pass


class UserRejectStrategy(FailureStrategy):
    """
    用户拒绝策略。

    因果链:
        触发条件: 用户主动选择"跳过"或"不想做"
        处理逻辑: 降低任务权重，减少未来推荐频率
        失效条件: 如果连续多次拒绝，可能需要移除任务
    """

    def can_handle(self, context: FailureContext) -> bool:
        return context.failure_type == FailureType.USER_REJECT

    def handle(self, context: FailureContext) -> HandlingResult:
        # 根据拒绝次数调整策略
        if context.failure_count >= 3:
            return HandlingResult(
                task_id=context.task_id,
                action="archive",
                rationale="用户连续 3 次拒绝此类任务，暂时归档",
                confidence=0.9,
                metadata={"archive_reason": "repeated_rejection"}
            )

        return HandlingResult(
            task_id=context.task_id,
            action="reduce_weight",
            rationale=f"用户主动跳过（第 {context.failure_count} 次），降低推荐权重",
            confidence=0.85
        )


class ContextMismatchStrategy(FailureStrategy):
    """
    上下文不匹配策略。

    因果链:
        触发条件: 客观条件不满足（如：需要特定设备、地点、天气等）
        处理逻辑: 保留任务权重，记录阻塞原因，寻找替代方案
        失效条件: 如果阻塞条件长期存在，可能需要重新评估任务可行性
    """

    def can_handle(self, context: FailureContext) -> bool:
        return context.failure_type == FailureType.CONTEXT_MISMATCH

    def handle(self, context: FailureContext) -> HandlingResult:
        return HandlingResult(
            task_id=context.task_id,
            action="find_alternative",
            rationale=f"客观条件不满足: {context.reason}。权重保留，寻找替代方案",
            confidence=0.7,
            metadata={
                "blocker": context.reason,
                "preserve_weight": True
            }
        )


class ResourceShortageStrategy(FailureStrategy):
    """
    资源不足策略。

    因果链:
        触发条件: 时间或精力不足
        处理逻辑: 重新调度到合适时间
        失效条件: 如果持续没有时间，可能需要调整任务优先级
    """

    def can_handle(self, context: FailureContext) -> bool:
        return context.failure_type == FailureType.RESOURCE_SHORTAGE

    def handle(self, context: FailureContext) -> HandlingResult:
        return HandlingResult(
            task_id=context.task_id,
            action="reschedule",
            rationale=f"资源不足: {context.reason}。重新调度到合适时间",
            confidence=0.75,
            metadata={"reschedule_reason": context.reason}
        )


class SystemErrorStrategy(FailureStrategy):
    """
    系统错误策略。

    因果链:
        触发条件: AI 规划错误或系统异常
        处理逻辑: 移除无效任务，记录日志用于改进
        失效条件: 不适用
    """

    def can_handle(self, context: FailureContext) -> bool:
        return context.failure_type == FailureType.SYSTEM_ERROR

    def handle(self, context: FailureContext) -> HandlingResult:
        from core.llm_adapter import get_llm

        reason = context.reason
        advice = "建议检查日志并修正逻辑"

        # 使用 Coding Hands (Claude) 分析系统错误
        try:
            llm = get_llm("coding_hands")
            if llm.get_model_name() != "rule_based":
                prompt = f"""系统错误分析:
任务ID: {context.task_id}
错误原因: {context.reason}
原始任务: {str(context.original_task)}

请作为资深工程师分析此错误，并给出具体的修复建议或代码片段。简明扼要。"""

                response = llm.generate(prompt, max_tokens=300)
                if response.success:
                    advice = response.content.strip()
        except Exception:
            pass

        return HandlingResult(
            task_id=context.task_id,
            action="remove_and_log",
            rationale=f"系统/规划错误: {reason}\nAI 诊断建议: {advice}",
            confidence=0.95,
            metadata={"error_type": "planning_error", "ai_advice": advice}
        )


class FailureHandler:
    """
    失败处理器（策略调度器）。

    使用方式:
        handler = FailureHandler()
        result = handler.handle(context)
    """

    def __init__(self):
        # 按优先级排序的策略列表
        self._strategies: List[FailureStrategy] = [
            SystemErrorStrategy(),
            UserRejectStrategy(),
            ContextMismatchStrategy(),
            ResourceShortageStrategy(),
        ]

    def handle(self, context: FailureContext) -> HandlingResult:
        """
        根据失败类型选择合适的策略处理。

        Args:
            context: 失败上下文

        Returns:
            处理结果
        """
        for strategy in self._strategies:
            if strategy.can_handle(context):
                return strategy.handle(context)

        # 兜底：未知类型
        return HandlingResult(
            task_id=context.task_id,
            action="log_only",
            rationale=f"未知失败类型: {context.failure_type.value}",
            confidence=0.5
        )

    @staticmethod
    def classify_failure(legacy_type: str) -> FailureType:
        """
        将旧版失败类型映射到新的枚举。

        用于兼容旧数据。
        """
        mapping = {
            "skipped": FailureType.USER_REJECT,
            "blocked": FailureType.CONTEXT_MISMATCH,
            "timeout": FailureType.RESOURCE_SHORTAGE,
            "invalid_plan": FailureType.SYSTEM_ERROR,
        }
        return mapping.get(legacy_type, FailureType.UNKNOWN)
