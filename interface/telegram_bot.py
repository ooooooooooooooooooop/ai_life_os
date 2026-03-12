"""
Telegram Bot Webhook Handler for AI Life OS.

挂载到 FastAPI,接收 Telegram 的 Webhook 回调。
用户通过 Telegram 发消息 → 写入事件日志 → Guardian 可感知。

支持的用户指令:
  /status     - 查询当前系统状态摘要
  /report <内容> - 上报行为事件(如"刚刷了30分钟手机")
  /help       - 指令帮助
  任意文本    - 视为行为上报
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Response

logger = logging.getLogger("telegram_bot")

router = APIRouter()


# ------------------------------------------------------------------ #
# Webhook 端点
# ------------------------------------------------------------------ #

@router.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    """
    接收 Telegram Webhook 推送。
    URL: /telegram/webhook/{bot_token}
    Telegram 会向此 URL POST Update 对象。
    """
    from core.telegram_config import get_telegram_config

    cfg = get_telegram_config()
    expected_token = cfg.get("bot_token", "")

    if expected_token and token != expected_token:
        logger.warning("Telegram webhook token 不匹配")
        return Response(status_code=403)

    try:
        update: Dict[str, Any] = await request.json()
    except Exception:
        return Response(status_code=400)

    await _handle_update(update)
    # Telegram 要求返回 200,否则会重试
    return Response(status_code=200)


# ------------------------------------------------------------------ #
# Update 处理
# ------------------------------------------------------------------ #

async def _handle_update(update: Dict[str, Any]) -> None:
    """处理 Telegram Update 对象。"""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = str(message.get("chat", {}).get("id", ""))
    text: str = message.get("text", "").strip()
    from_user = message.get("from", {})
    username = from_user.get("username") or from_user.get("first_name", "unknown")

    if not text:
        return

    logger.info("Telegram 消息来自 %s: %s", username, text[:80])

    if text.startswith("/status"):
        await _cmd_status(chat_id)
    elif text.startswith("/report"):
        content = text[len("/report"):].strip()
        await _cmd_report(chat_id, content or text, username)
    elif text.startswith("/help"):
        await _cmd_help(chat_id)
    else:
        # 默认视为行为上报
        await _cmd_report(chat_id, text, username)


# ------------------------------------------------------------------ #
# 指令处理
# ------------------------------------------------------------------ #

async def _cmd_status(chat_id: str) -> None:
    """返回系统状态摘要。"""
    try:
        from core.snapshot_manager import load_latest_snapshot
        snapshot = load_latest_snapshot()
        if snapshot:
            msg = (
                "📊 *系统状态*\n\n"
                f"当前阶段: {snapshot.get('current_phase', '未知')}\n"
                f"活跃目标: {len(snapshot.get('goals', []))} 个\n"
                f"更新时间: {snapshot.get('updated_at', '未知')[:16]}"
            )
        else:
            msg = "📊 暂无快照数据"
    except Exception as e:
        logger.error("获取状态失败: %s", e)
        msg = "⚠️ 获取状态失败,请稍后再试"

    _reply(chat_id, msg)


async def _cmd_report(chat_id: str, content: str, username: str) -> None:
    """将用户上报内容写入事件日志。"""
    if not content:
        _reply(chat_id, "请提供上报内容,例如:/report 刚刷了30分钟手机")
        return

    try:
        from core.event_sourcing import append_event, EVENT_SCHEMA_VERSION
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_type": "user_report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "telegram",
            "data": {
                "content": content,
                "username": username,
                "raw_text": content,
            },
            "audit": {
                "channel": "telegram",
                "auto": False,
            }
        }
        append_event(event)
        _reply(chat_id, f"✅ 已记录:{content[:100]}")
        logger.info("事件已写入: user_report via telegram")
    except Exception as e:
        logger.error("写入事件失败: %s", e)
        _reply(chat_id, "⚠️ 记录失败,请稍后再试")


async def _cmd_help(chat_id: str) -> None:
    """发送帮助文本。"""
    msg = (
        "🤖 *AI Life OS Bot*\n\n"
        "可用指令:\n"
        "`/status` — 查看当前系统状态\n"
        "`/report <内容>` — 上报行为(如:刚刷了30分钟手机)\n"
        "`/help` — 显示此帮助\n\n"
        "也可以直接发送文字,会自动作为行为上报记录。"
    )
    _reply(chat_id, msg)


# ------------------------------------------------------------------ #
# 工具函数
# ------------------------------------------------------------------ #

def _reply(chat_id: str, text: str) -> None:
    """通过 TelegramNotifier 回复消息。"""
    try:
        from core.telegram_config import get_telegram_config
        from interface.notifiers.telegram_notifier import TelegramNotifier

        cfg = get_telegram_config()
        notifier = TelegramNotifier({
            "bot_token": cfg.get("bot_token", ""),
            "chat_id": chat_id,
            "enabled": True,
        })
        notifier.send_raw(text)
    except Exception as e:
        logger.error("回复失败: %s", e)
