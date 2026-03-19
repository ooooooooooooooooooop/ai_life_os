"""
企业微信数据模型 for AI Life OS.

定义企业微信相关的数据结构，包括配置、消息、API 响应等。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class WeComConfig:
    """企业微信配置模型"""
    corp_id: str              # 企业 ID
    corp_secret: str          # 应用 Secret
    agent_id: str             # 应用 AgentId
    to_user: str = "@all"     # 默认推送对象
    token: str = ""           # 消息加密 Token（可选）
    encoding_aes_key: str = ""  # 消息加密 Key（可选）
    enabled: bool = False     # 是否启用

    def is_configured(self) -> bool:
        """检查必填配置是否完整"""
        return bool(self.corp_id) and bool(self.corp_secret) and bool(self.agent_id)


@dataclass
class WeComMessage:
    """企业微信消息模型"""
    to_user_name: str         # 消息接收者 ID
    from_user_name: str       # 消息发送者 ID
    create_time: int          # 消息创建时间戳
    msg_type: str             # 消息类型（text、image 等）
    content: Optional[str] = None    # 消息内容（文本消息）
    msg_id: Optional[int] = None     # 消息 ID
    agent_id: Optional[int] = None   # 应用 AgentID

    def get_create_datetime(self) -> datetime:
        """获取消息创建时间的 datetime 对象"""
        return datetime.fromtimestamp(self.create_time)


@dataclass
class WeComAPIResponse:
    """企业微信 API 响应模型"""
    errcode: int              # 错误码
    errmsg: str               # 错误信息
    access_token: Optional[str] = None  # access_token（仅 gettoken 接口）
    expires_in: Optional[int] = None    # 过期时间（仅 gettoken 接口）
    invaliduser: Optional[str] = None   # 无效用户 ID
    invalidparty: Optional[str] = None  # 无效部门 ID
    invalidtag: Optional[str] = None    # 无效标签 ID

    def is_success(self) -> bool:
        """检查 API 调用是否成功"""
        return self.errcode == 0


@dataclass
class WeComSendMessage:
    """企业微信发送消息模型"""
    touser: str               # 接收消息的用户 ID
    msgtype: str              # 消息类型
    agentid: int              # 应用 AgentID
    text: dict                # 消息内容（根据 msgtype 不同而不同）
    safe: int = 0             # 是否是保密消息（0-否，1-是）

    def to_dict(self) -> dict:
        """转换为字典格式，用于 API 调用"""
        return {
            "touser": self.touser,
            "msgtype": self.msgtype,
            "agentid": self.agentid,
            self.msgtype: self.text,
            "safe": self.safe
        }
