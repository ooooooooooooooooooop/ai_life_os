"""
企业微信 WebSocket 长连接服务启动脚本
"""
import asyncio
import logging
from interface.wecom_ws_client import WeComWebSocketClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def on_message(msg_data: dict):
    """消息回调函数"""
    logger.info(f"收到消息: {msg_data}")
    
    # TODO: 集成到 AI Life OS 的消息处理逻辑
    # 这里可以调用 AI Life OS 的核心功能处理消息


async def main():
    """主函数"""
    # 配置参数
    bot_id = "1000002"
    secret = "ytH5r7WKSmzoI9i2Zf4QOrVcC7gw_RMPjSP-XrCRc2E"
    
    # 创建客户端
    client = WeComWebSocketClient(
        bot_id=bot_id,
        secret=secret,
        on_message=on_message
    )
    
    logger.info("启动企业微信 WebSocket 客户端...")
    logger.info(f"bot_id: {bot_id}")
    logger.info("无需公网IP，无需域名备案")
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
