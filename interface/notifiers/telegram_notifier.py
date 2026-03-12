"""
Telegram Notifier for AI Life OS.

通过 Telegram Bot API 发送通知。
目前为接口层实现,不依赖 python-telegram-bot 库,
直接用 httpx 调用 Bot API。
"""
from importlib.util import find_spec
from typing import Any, Dict, Optional

from interface.notifiers.base import BaseNotifier, Notification, NotificationPriority


class TelegramNotifier(BaseNotifier):
    """通过 Telegram Bot 发送通知。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.bot_token: str = self.config.get("bot_token", "")
        self.chat_id: str = str(self.config.get("chat_id", ""))
        self.parse_mode: str = self.config.get("parse_mode", "Markdown")
        self._base_url = f"https://api.telegram.org/bot{self.bot_token}"

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def send(self, notification: Notification) -> bool:
        """发送通知消息。"""
        if not self.enabled or not self._is_configured():
            return False

        text = self._format_message(notification)
        return self._send_message(text)

    def send_raw(self, text: str) -> bool:
        """发送原始文本(Guardian 主动干预用)。"""
        if not self.enabled or not self._is_configured():
            return False
        return self._send_message(text)

    def get_name(self) -> str:
        return "telegram"

    def is_available(self) -> bool:
        return (
            self.enabled
            and self._is_configured()
            and find_spec("httpx") is not None
        )

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _is_configured(self) -> bool:
        return bool(self.bot_token) and bool(self.chat_id)

    def _format_message(self, notification: Notification) -> str:
        """将 Notification 格式化为 Telegram 消息文本。"""
        priority_emoji = {
            NotificationPriority.LOW: "💬",
            NotificationPriority.NORMAL: "📌",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.URGENT: "🚨",
        }.get(notification.priority, "📌")

        action_hint = "\n\n_需要你回应_" if notification.action_required else ""

        return (
            f"{priority_emoji} *{notification.title}*\n\n"
            f"{notification.message}"
            f"{action_hint}"
        )

    def _send_message(self, text: str) -> bool:
        """调用 Telegram sendMessage API。"""
        try:
            import httpx
        except ImportError:
            print("[TelegramNotifier] httpx 未安装,无法发送消息")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": self.parse_mode,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self._base_url}/sendMessage",
                    json=payload,
                )
                if resp.status_code == 200:
                    return True
                else:
                    print(f"[TelegramNotifier] API 错误: {resp.status_code} {resp.text}")
                    return False
        except Exception as e:
            print(f"[TelegramNotifier] 发送失败: {e}")
            return False
