"""
Desktop Notifier for AI Life OS.

Sends system notifications using platform-native APIs.
"""
import platform
from typing import Any, Dict, Optional

from interface.notifiers.base import BaseNotifier, Notification


class DesktopNotifier(BaseNotifier):
    """Send notifications via system desktop notifications."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._plyer_available = False
        self._win10toast_available = False
        
        # 尝试导入通知库
        try:
            import plyer
            self._plyer_available = True
        except ImportError:
            pass
        
        if platform.system() == "Windows":
            try:
                from win10toast import ToastNotifier
                self._win10toast_available = True
            except ImportError:
                pass
    
    def send(self, notification: Notification) -> bool:
        """Send a desktop notification."""
        if not self.enabled:
            return False
        
        # 优先使用 win10toast (Windows)
        if self._win10toast_available:
            return self._send_win10toast(notification)
        
        # 使用 plyer (跨平台)
        if self._plyer_available:
            return self._send_plyer(notification)
        
        # 降级：打印到控制台
        print(f"\n🔔 [通知] {notification.title}")
        print(f"   {notification.message}\n")
        return True
    
    def _send_win10toast(self, notification: Notification) -> bool:
        """Send via win10toast."""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            
            # 根据优先级设置持续时间
            duration = {
                "low": 3,
                "normal": 5,
                "high": 8,
                "urgent": 10
            }.get(notification.priority.value, 5)
            
            toaster.show_toast(
                notification.title,
                notification.message,
                duration=duration,
                threaded=True
            )
            return True
        except Exception as e:
            print(f"[通知错误] win10toast: {e}")
            return False
    
    def _send_plyer(self, notification: Notification) -> bool:
        """Send via plyer."""
        try:
            from plyer import notification as plyer_notify
            
            plyer_notify.notify(
                title=notification.title,
                message=notification.message,
                app_name="AI Life OS",
                timeout=5
            )
            return True
        except Exception as e:
            print(f"[通知错误] plyer: {e}")
            return False
    
    def get_name(self) -> str:
        return "desktop"
    
    def is_available(self) -> bool:
        return self.enabled and (
            self._plyer_available or 
            self._win10toast_available or 
            True  # 总是可用（降级到控制台输出）
        )
