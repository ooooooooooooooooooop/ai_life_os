"""
Base Notifier for AI Life OS.

Defines the base interface for all notifiers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """A notification to be sent."""
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    created_at: str = None
    action_required: bool = False
    data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class BaseNotifier(ABC):
    """Base class for all notifiers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """
        Send a notification.

        Args:
            notification: The notification to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the notifier name."""
        pass

    def is_available(self) -> bool:
        """Check if this notifier is available for use."""
        return self.enabled
