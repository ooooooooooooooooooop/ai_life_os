"""
LLM 反馈分类器 - 将用户自由文本反馈识别为结构化意图。

支持意图:
- complete: 已完成
- skip: 跳过/不想做
- defer: 延期/稍后
- partial: 部分完成
- blocked: 被阻塞
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass

from core.llm_adapter import get_llm
from core.utils import parse_llm_json


class FeedbackIntent(str, Enum):
    COMPLETE = "complete"
    SKIP = "skip"
    DEFER = "defer"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class FeedbackResult:
    intent: FeedbackIntent
    confidence: float
    extracted_reason: Optional[str] = None
    defer_until: Optional[str] = None  # ISO 格式日期
    progress_percent: Optional[int] = None  # 仅 partial 时有效


# 规则优先匹配 (快速路径，避免 LLM 调用)
RULE_PATTERNS = {
    FeedbackIntent.COMPLETE: [
        "完成", "搞定", "done", "finished", "完了", "ok", "好了", "✓", "✅"
    ],
    FeedbackIntent.SKIP: [
        "跳过", "不做", "skip", "取消", "算了", "不想", "放弃"
    ],
    FeedbackIntent.DEFER: [
        "明天", "稍后", "later", "下次", "改天", "等", "之后", "待会"
    ],
    FeedbackIntent.BLOCKED: [
        "没有", "缺", "等待", "blocked", "阻塞", "需要", "依赖"
    ],
}


def classify_feedback(message: str) -> FeedbackResult:
    """
    将用户自由文本分类为结构化反馈意图。
    
    实现策略:
    1. 规则匹配 (快速路径)
    2. LLM 分类 (复杂情况)
    """
    message_lower = message.lower().strip()
    
    # 1. 规则匹配
    for intent, patterns in RULE_PATTERNS.items():
        for pattern in patterns:
            if pattern in message_lower:
                return FeedbackResult(
                    intent=intent,
                    confidence=0.9,
                    extracted_reason=message
                )
    
    # 2. 检测进度百分比 (partial)
    import re
    progress_match = re.search(r'(\d{1,3})\s*[%％]', message)
    if progress_match:
        percent = int(progress_match.group(1))
        if 0 < percent < 100:
            return FeedbackResult(
                intent=FeedbackIntent.PARTIAL,
                confidence=0.95,
                progress_percent=percent,
                extracted_reason=message
            )
    
    # 3. LLM 分类 (复杂情况)
    return _llm_classify(message)


def _llm_classify(message: str) -> FeedbackResult:
    """使用 LLM 进行复杂文本分类"""
    llm = get_llm("simple_local")
    
    # 规则模式降级
    if llm.get_model_name() == "rule_based":
        return FeedbackResult(
            intent=FeedbackIntent.UNKNOWN,
            confidence=0.0,
            extracted_reason=message
        )
    
    system_prompt = """你是一个任务反馈分类器。根据用户的反馈文本，判断其意图。

可能的意图:
- complete: 任务已完成
- skip: 用户决定跳过此任务
- defer: 用户想延期执行
- partial: 任务部分完成
- blocked: 任务被外部因素阻塞

返回 JSON 格式:
{
  "intent": "complete|skip|defer|partial|blocked",
  "confidence": 0.0-1.0,
  "reason": "简短原因",
  "defer_until": "可选，ISO日期",
  "progress_percent": 可选，0-100整数
}"""

    prompt = f"用户反馈: \"{message}\""
    
    try:
        response = llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=200
        )
        
        if response.success and response.content:
            result = parse_llm_json(response.content)
            if result:
                intent_str = result.get("intent", "unknown")
                try:
                    intent = FeedbackIntent(intent_str)
                except ValueError:
                    intent = FeedbackIntent.UNKNOWN
                
                return FeedbackResult(
                    intent=intent,
                    confidence=result.get("confidence", 0.5),
                    extracted_reason=result.get("reason"),
                    defer_until=result.get("defer_until"),
                    progress_percent=result.get("progress_percent")
                )
    except Exception as e:
        print(f"[FeedbackClassifier] LLM 分类失败: {e}")
    
    return FeedbackResult(
        intent=FeedbackIntent.UNKNOWN,
        confidence=0.0,
        extracted_reason=message
    )
