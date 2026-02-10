"""
Webhook Notifier for AI Life OS.

Sends notifications via HTTP webhooks (e.g., Slack, Discord, custom endpoints).
"""
from importlib.util import find_spec
from typing import Any, Dict, Optional

from interface.notifiers.base import BaseNotifier, Notification


class WebhookNotifier(BaseNotifier):
    """Send notifications via HTTP webhooks."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.webhook_url = self.config.get("webhook_url", "")
        self.webhook_type = self.config.get("type", "generic")  # generic, slack, discord

    def send(self, notification: Notification) -> bool:
        """Send a webhook notification."""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            import httpx
        except ImportError:
            print("[通知错误] httpx not installed")
            return False

        payload = self._build_payload(notification)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code < 400
        except Exception as e:
            print(f"[通知错误] Webhook: {e}")
            return False

    def _build_payload(self, notification: Notification) -> Dict[str, Any]:
        """Build webhook payload based on type."""
        if self.webhook_type == "slack":
            return {
                "text": f"*{notification.title}*\n{notification.message}"
            }
        elif self.webhook_type == "discord":
            return {
                "content": f"**{notification.title}**\n{notification.message}"
            }
        else:
            # Generic webhook
            return {
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "timestamp": notification.created_at,
                "action_required": notification.action_required
            }

    def get_name(self) -> str:
        return "webhook"

    def is_available(self) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        return find_spec("httpx") is not None
