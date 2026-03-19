"""
企业微信 Bot Webhook Handler for AI Life OS.

挂载到 FastAPI,接收企业微信的 Webhook 回调。
用户通过企业微信发消息 → 写入事件日志 → Guardian 可感知。

支持的用户指令:
  "今天" / "任务" - 查询今日任务计划
  任意文本 - 视为行为上报，调用 InteractionHandler 处理
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Query, Request, Response

logger = logging.getLogger("wecom_bot")

router = APIRouter()


# ------------------------------------------------------------------ #
# Webhook 端点
# ------------------------------------------------------------------ #

@router.get("/webhook")
async def verify_url(
    msg_signature: Optional[str] = Query(None),
    timestamp: Optional[str] = Query(None),
    nonce: Optional[str] = Query(None),
    echostr: Optional[str] = Query(None)
):
    """
    企业微信 URL 验证接口。

    企业微信在配置回调 URL 时会发送 GET 请求进行验证。
    需要验证签名并解密echostr后返回。

    Args:
        msg_signature: 消息签名
        timestamp: 时间戳
        nonce: 随机数
        echostr: 加密的随机字符串

    Returns:
        解密后的echostr值
    """
    logger.info("企业微信 URL 验证请求")
    logger.info(f"参数: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr}")

    # 检查必需参数
    if not all([msg_signature, timestamp, nonce, echostr]):
        logger.error("缺少必需参数")
        return Response(content="missing query params", status_code=400, media_type="text/plain")

    try:
        import yaml
        from interface.wecom_crypto import WeComCrypto
        
        # 加载配置
        with open('config/wecom.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        token = config.get('token', '')
        encoding_aes_key = config.get('encoding_aes_key', '')
        corp_id = config.get('corp_id', '')
        
        if not token or not encoding_aes_key:
            logger.error("缺少token或encoding_aes_key配置")
            return Response(content="wecom not configured", status_code=500, media_type="text/plain")
        
        # 创建加解密器
        crypto = WeComCrypto(token, encoding_aes_key, corp_id)
        
        # 验证签名
        if not crypto.verify_signature(timestamp, nonce, echostr, msg_signature):
            logger.error(f"签名验证失败: expected={crypto.compute_signature(timestamp, nonce, echostr)}, got={msg_signature}")
            return Response(content="unauthorized", status_code=401, media_type="text/plain")
        
        # 解密echostr
        decrypted_echostr, receive_id = crypto.decrypt_url(echostr)
        logger.info(f"签名验证成功，解密echostr: {decrypted_echostr}, receive_id: {receive_id}")
        
        # 返回解密后的明文
        return Response(content=decrypted_echostr, media_type="text/plain; charset=utf-8")
    
    except Exception as e:
        logger.error(f"URL验证异常: {e}", exc_info=True)
        return Response(content=str(e) or "decrypt failed", status_code=400, media_type="text/plain")


@router.post("/webhook")
async def receive_message(request: Request):
    """
    接收企业微信推送的用户消息。

    企业微信会将用户发送的消息以 POST 请求推送到此接口。
    消息体为 XML 格式。

    Returns:
        XML 格式的回复消息
    """
    logger.info("接收到企业微信消息推送")

    try:
        # 读取请求体
        xml_content = await request.body()
        xml_str = xml_content.decode('utf-8')

        # 解析 XML 消息
        msg_dict = _parse_xml_message(xml_str)
        if not msg_dict:
            logger.error("XML 解析失败")
            return Response(content="", media_type="application/xml")

        logger.info(f"收到消息: {msg_dict.get('content', '')[:50]}")

        # 处理消息
        reply_xml = await _handle_message(msg_dict)

        # 返回 XML 回复
        return Response(content=reply_xml, media_type="application/xml")

    except Exception as e:
        logger.error(f"处理企业微信消息异常: {e}", exc_info=True)
        return Response(content="", media_type="application/xml")


# ------------------------------------------------------------------ #
# 消息处理
# ------------------------------------------------------------------ #

async def _handle_message(msg_dict: Dict) -> str:
    """
    处理接收到的消息。

    Args:
        msg_dict: 解析后的消息字典

    Returns:
        XML 格式的回复消息
    """
    from_user = msg_dict.get("from_user_name", "")
    to_user = msg_dict.get("to_user_name", "")
    content = msg_dict.get("content", "")
    msg_type = msg_dict.get("msg_type", "text")

    # 只处理文本消息
    if msg_type != "text":
        logger.info(f"忽略非文本消息: {msg_type}")
        return ""

    # 记录消息到事件日志
    await _log_message_to_event_log(msg_dict)

    # 指令路由
    reply_content = ""

    if content in ["今天", "任务"]:
        # 调用 Steward 生成今日任务计划
        reply_content = await _get_today_plan()
    else:
        # 调用 InteractionHandler 处理
        reply_content = await _handle_user_message(content, from_user)

    # 构造 XML 回复
    if reply_content:
        return _build_xml_response(to_user=from_user, from_user=to_user, content=reply_content)
    else:
        return ""


async def _log_message_to_event_log(msg_dict: Dict) -> None:
    """
    将消息记录到事件日志。

    Args:
        msg_dict: 消息字典
    """
    try:
        from core.event_logger import log_event

        event_data = {
            "source": "wecom",
            "from_user": msg_dict.get("from_user_name"),
            "to_user": msg_dict.get("to_user_name"),
            "content": msg_dict.get("content"),
            "msg_type": msg_dict.get("msg_type"),
            "create_time": msg_dict.get("create_time")
        }

        log_event(
            event_type="wecom_message_received",
            data=event_data,
            source="wecom_bot"
        )

        logger.info("消息已记录到事件日志")

    except Exception as e:
        logger.error(f"记录事件日志失败: {e}")


async def _get_today_plan() -> str:
    """
    获取今日任务计划。

    Returns:
        今日任务计划的文本
    """
    try:
        # TODO: 调用 Steward 生成今日任务计划
        # from core.steward import Steward
        # steward = Steward()
        # plan = steward.generate_today_plan()
        # return plan

        # 临时返回
        return "今日任务计划功能正在开发中，敬请期待！"

    except Exception as e:
        logger.error(f"生成今日任务计划失败: {e}")
        return "抱歉，无法生成今日任务计划，请稍后重试。"


async def _handle_user_message(content: str, from_user: str) -> str:
    """
    处理用户消息。

    Args:
        content: 消息内容
        from_user: 发送者 ID

    Returns:
        回复内容
    """
    try:
        # TODO: 调用 InteractionHandler 处理
        # from core.interaction_handler import InteractionHandler
        # handler = InteractionHandler()
        # reply = handler.handle(content, from_user)
        # return reply

        # 临时返回
        return f"收到您的消息：{content}\n\n系统正在开发中，感谢您的耐心等待！"

    except Exception as e:
        logger.error(f"处理用户消息失败: {e}")
        return "系统繁忙，请稍后重试。"


# ------------------------------------------------------------------ #
# XML 解析和构造
# ------------------------------------------------------------------ #

def _parse_xml_message(xml_content: str) -> Optional[Dict]:
    """
    解析企业微信 XML 消息体。

    Args:
        xml_content: XML 字符串

    Returns:
        消息字典，如果解析失败则返回 None
    """
    try:
        root = ET.fromstring(xml_content)

        # 提取关键字段
        msg_dict = {
            "to_user_name": _get_xml_text(root, "ToUserName"),
            "from_user_name": _get_xml_text(root, "FromUserName"),
            "create_time": int(_get_xml_text(root, "CreateTime") or "0"),
            "msg_type": _get_xml_text(root, "MsgType"),
            "content": _get_xml_text(root, "Content"),
            "msg_id": _get_xml_text(root, "MsgId"),
            "agent_id": _get_xml_text(root, "AgentID")
        }

        return msg_dict

    except ET.ParseError as e:
        logger.error(f"XML 解析错误: {e}")
        return None
    except Exception as e:
        logger.error(f"解析 XML 消息异常: {e}")
        return None


def _get_xml_text(element: ET.Element, tag: str) -> str:
    """
    从 XML 元素中获取指定标签的文本内容。

    Args:
        element: XML 元素
        tag: 标签名

    Returns:
        文本内容，如果不存在则返回空字符串
    """
    child = element.find(tag)
    if child is not None and child.text:
        return child.text
    return ""


def _build_xml_response(to_user: str, from_user: str, content: str) -> str:
    """
    构造 XML 回复消息。

    Args:
        to_user: 接收者 ID
        from_user: 发送者 ID
        content: 回复内容

    Returns:
        XML 字符串
    """
    create_time = int(datetime.now().timestamp())

    xml_template = """<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{create_time}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""

    return xml_template.format(
        to_user=to_user,
        from_user=from_user,
        create_time=create_time,
        content=content
    )
