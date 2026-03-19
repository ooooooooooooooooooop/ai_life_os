"""
企业微信消息推送器 for AI Life OS.

通过企业微信 API 发送通知消息。
"""
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import yaml

from interface.notifiers.base import BaseNotifier, Notification, NotificationPriority
from interface.wecom_models import WeComAPIResponse, WeComConfig, WeComSendMessage


class WeComNotifier(BaseNotifier):
    """通过企业微信发送通知。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化企业微信消息推送器。

        Args:
            config: 配置字典，如果为 None 则从配置文件加载
        """
        super().__init__(config)

        # 如果未提供配置，从配置文件加载
        if not self.config:
            self.config = self._load_config_from_file()

        # 初始化配置
        self.wecom_config = WeComConfig(
            corp_id=self.config.get("corp_id", ""),
            corp_secret=self.config.get("corp_secret", ""),
            agent_id=self.config.get("agent_id", ""),
            to_user=self.config.get("to_user", "@all"),
            token=self.config.get("token", ""),
            encoding_aes_key=self.config.get("encoding_aes_key", ""),
            enabled=self.config.get("enabled", False)
        )

        # 缓存属性
        self._access_token: Optional[str] = None
        self._token_expire_time: Optional[datetime] = None

        # API 基础 URL
        self._base_url = "https://qyapi.weixin.qq.com/cgi-bin"

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def send(self, notification: Notification) -> bool:
        """
        发送结构化通知。

        Args:
            notification: 通知对象

        Returns:
            True 如果发送成功，False 否则
        """
        if not self.enabled or not self.is_available():
            return False

        # 格式化消息
        text = self._format_message(notification)
        return self.send_raw(text)

    def send_raw(self, text: str, to_user: Optional[str] = None) -> bool:
        """
        发送原始文本消息。

        Args:
            text: 文本内容
            to_user: 推送对象，为 None 时使用默认配置

        Returns:
            True 如果发送成功，False 否则
        """
        if not self.enabled or not self.is_available():
            return False

        # 使用默认推送对象或指定对象
        target_user = to_user if to_user else self.wecom_config.to_user

        return self._send_message(text, target_user)

    def get_name(self) -> str:
        """返回推送器名称"""
        return "wecom"

    def is_available(self) -> bool:
        """检查推送器是否可用"""
        return (
            self.enabled
            and self.wecom_config.is_configured()
            and self._check_httpx_available()
        )

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _load_config_from_file(self) -> Dict[str, Any]:
        """从配置文件加载配置"""
        config_path = "config/wecom.yaml"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"[WeComNotifier] 配置文件不存在: {config_path}")
            return {}
        except Exception as e:
            print(f"[WeComNotifier] 加载配置文件失败: {e}")
            return {}

    def _check_httpx_available(self) -> bool:
        """检查 httpx 是否可用"""
        try:
            from importlib.util import find_spec
            return find_spec("httpx") is not None
        except ImportError:
            return False

    def _format_message(self, notification: Notification) -> str:
        """将 Notification 格式化为企业微信消息文本"""
        priority_emoji = {
            NotificationPriority.LOW: "💬",
            NotificationPriority.NORMAL: "📌",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.URGENT: "🚨",
        }.get(notification.priority, "📌")

        action_hint = "\n\n【需要你回应】" if notification.action_required else ""

        return (
            f"{priority_emoji} {notification.title}\n\n"
            f"{notification.message}"
            f"{action_hint}"
        )

    def _get_access_token(self) -> Optional[str]:
        """
        获取 access_token，带缓存机制。

        Returns:
            access_token 字符串，如果获取失败则返回 None
        """
        # 检查缓存的 token 是否有效（提前 5 分钟刷新）
        if self._access_token and self._token_expire_time:
            if datetime.now() < self._token_expire_time - timedelta(minutes=5):
                return self._access_token

        # 调用企业微信 API 获取新的 access_token
        try:
            import httpx
        except ImportError:
            print("[WeComNotifier] httpx 未安装，无法获取 access_token")
            return None

        url = f"{self._base_url}/gettoken"
        params = {
            "corpid": self.wecom_config.corp_id,
            "corpsecret": self.wecom_config.corp_secret
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    api_response = WeComAPIResponse(
                        errcode=data.get("errcode", -1),
                        errmsg=data.get("errmsg", ""),
                        access_token=data.get("access_token"),
                        expires_in=data.get("expires_in")
                    )

                    if api_response.is_success() and api_response.access_token:
                        # 缓存 access_token 和过期时间
                        self._access_token = api_response.access_token
                        self._token_expire_time = datetime.now() + timedelta(
                            seconds=api_response.expires_in or 7200
                        )
                        print(f"[WeComNotifier] 成功获取 access_token，有效期 {api_response.expires_in} 秒")
                        return self._access_token
                    else:
                        print(f"[WeComNotifier] 获取 access_token 失败: {api_response.errcode} - {api_response.errmsg}")
                        return None
                else:
                    print(f"[WeComNotifier] API 请求失败: {resp.status_code} {resp.text}")
                    return None
        except Exception as e:
            print(f"[WeComNotifier] 获取 access_token 异常: {e}")
            return None

    def _send_message(self, text: str, to_user: str) -> bool:
        """
        调用企业微信 API 发送消息，带重试机制。

        Args:
            text: 消息内容
            to_user: 推送对象

        Returns:
            True 如果发送成功，False 否则
        """
        # 获取 access_token
        access_token = self._get_access_token()
        if not access_token:
            print("[WeComNotifier] 无法获取 access_token，消息发送失败")
            return False

        try:
            import httpx
        except ImportError:
            print("[WeComNotifier] httpx 未安装，无法发送消息")
            return False

        # 构造消息体
        message = WeComSendMessage(
            touser=to_user,
            msgtype="text",
            agentid=int(self.wecom_config.agent_id),
            text={"content": text}
        )

        url = f"{self._base_url}/message/send"
        params = {"access_token": access_token}

        # 重试机制：最多 3 次
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(url, params=params, json=message.to_dict())

                    if resp.status_code == 200:
                        data = resp.json()
                        api_response = WeComAPIResponse(
                            errcode=data.get("errcode", -1),
                            errmsg=data.get("errmsg", ""),
                            invaliduser=data.get("invaliduser"),
                            invalidparty=data.get("invalidparty"),
                            invalidtag=data.get("invalidtag")
                        )

                        if api_response.is_success():
                            print(f"[WeComNotifier] 消息发送成功")
                            return True
                        else:
                            # 如果是 access_token 过期，清除缓存并重试
                            if api_response.errcode in [40014, 42001]:
                                print(f"[WeComNotifier] access_token 已过期，重新获取")
                                self._access_token = None
                                self._token_expire_time = None
                                access_token = self._get_access_token()
                                if not access_token:
                                    return False
                                params = {"access_token": access_token}
                                continue
                            else:
                                print(f"[WeComNotifier] 消息发送失败: {api_response.errcode} - {api_response.errmsg}")
                                if attempt < max_retries - 1:
                                    print(f"[WeComNotifier] 等待 1 秒后重试 ({attempt + 1}/{max_retries})")
                                    time.sleep(1)
                                    continue
                                return False
                    else:
                        print(f"[WeComNotifier] API 请求失败: {resp.status_code} {resp.text}")
                        if attempt < max_retries - 1:
                            print(f"[WeComNotifier] 等待 1 秒后重试 ({attempt + 1}/{max_retries})")
                            time.sleep(1)
                            continue
                        return False
            except Exception as e:
                print(f"[WeComNotifier] 发送消息异常: {e}")
                if attempt < max_retries - 1:
                    print(f"[WeComNotifier] 等待 1 秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(1)
                    continue
                return False

        return False
