"""
Conversation Summarizer - 对话记忆摘要

将用户对话写入事件日志并索引到 memory_store。
"""


def summarize_and_save(message: str, response: str, intent: str, mood: str = "neutral") -> None:
    """
    将对话轮次写入事件日志并同步到 memory。

    Args:
        message: 用户消息
        response: AI 回复
        intent: 意图类型
        mood: 情绪状态（stressed/low/positive/neutral）
    """
    try:
        from core.event_sourcing import append_event

        # 1. 写入事件日志
        event = {
            "type": "conversation_turn",
            "user_message": message,
            "ai_response": response,
            "intent": intent,
            "mood": mood,
        }
        append_event(event)

        # 2. 同步到 memory_store
        try:
            from core.memory_indexer import sync_memory as do_sync_memory
            do_sync_memory()
        except Exception:
            # memory 索引失败不影响主流程
            pass

    except Exception:
        # 全程失败不影响主流程
        pass
