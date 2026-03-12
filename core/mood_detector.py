"""
Mood Detector - 情绪状态感知

基于关键词的轻量级情绪检测（不调用 LLM）。
"""

# 情绪关键词映射
MOOD_KEYWORDS = {
    "stressed": ["好累", "压力", "焦虑", "不行了", "撑不住", "烦"],
    "low": ["没意思", "放弃", "算了", "躺平", "不想动"],
    "positive": ["做到了", "完成了", "爽", "冲", "搞定"],
}


def detect_mood(message: str) -> str:
    """
    检测用户消息中的情绪状态。

    Args:
        message: 用户消息

    Returns:
        情绪状态: "stressed" | "low" | "positive" | "neutral"
    """
    if not message:
        return "neutral"

    message_lower = message.lower()

    # 按优先级检测：stressed > low > positive
    for mood, keywords in MOOD_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                return mood

    return "neutral"
