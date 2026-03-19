"""
企业微信 WebSocket 长连接客户端

参考 OpenClaw China 实现
无需公网IP，无需域名备案
"""
import asyncio
import json
import time
import hashlib
from typing import Optional, Callable, Dict, Any
import websockets
from websockets.client import WebSocketClientProtocol
import logging

logger = logging.getLogger(__name__)


class WeComWebSocketClient:
    """企业微信 WebSocket 长连接客户端"""
    
    WS_URL = "wss://openws.work.weixin.qq.com"
    HEARTBEAT_INTERVAL = 30  # 秒
    RECONNECT_DELAY = 1  # 秒
    MAX_RECONNECT_DELAY = 30  # 秒
    
    def __init__(
        self,
        bot_id: str,
        secret: str,
        ws_url: str = WS_URL,
        heartbeat_interval: int = HEARTBEAT_INTERVAL,
        on_message: Optional[Callable] = None
    ):
        """
        初始化 WebSocket 客户端
        
        Args:
            bot_id: 机器人ID (AgentId)
            secret: 机器人密钥
            ws_url: WebSocket服务器地址
            heartbeat_interval: 心跳间隔(秒)
            on_message: 消息回调函数
        """
        self.bot_id = bot_id
        self.secret = secret
        self.ws_url = ws_url
        self.heartbeat_interval = heartbeat_interval
        self.on_message = on_message
        
        self.ws: Optional[WebSocketClientProtocol] = None
        self.running = False
        self.req_id = 0
        self.reconnect_delay = self.RECONNECT_DELAY
        
    def _get_req_id(self) -> str:
        """获取请求ID"""
        self.req_id += 1
        return f"{int(time.time() * 1000)}_{self.req_id}"
    
    def _sign(self, timestamp: str) -> str:
        """
        计算签名
        
        Args:
            timestamp: 时间戳
        
        Returns:
            签名字符串
        """
        # 签名算法: sha256(bot_id + timestamp + secret)
        data = f"{self.bot_id}{timestamp}{self.secret}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def connect(self) -> bool:
        """
        连接 WebSocket 服务器
        
        Returns:
            True 如果连接成功
        """
        try:
            logger.info(f"正在连接企业微信 WebSocket: {self.ws_url}")
            
            # 连接 WebSocket
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=None,  # 禁用默认ping，使用自定义心跳
                ping_timeout=None
            )
            
            logger.info("WebSocket 连接成功")
            
            # 发送认证请求
            timestamp = str(int(time.time()))
            sign = self._sign(timestamp)
            
            auth_msg = {
                "cmd": "init",
                "req_id": self._get_req_id(),
                "data": {
                    "bot_id": self.bot_id,
                    "timestamp": timestamp,
                    "sign": sign
                }
            }
            
            await self.ws.send(json.dumps(auth_msg))
            logger.info(f"已发送认证请求: bot_id={self.bot_id}")
            
            # 等待认证响应
            response = await self.ws.recv()
            resp_data = json.loads(response)
            
            if resp_data.get("cmd") == "init" and resp_data.get("code") == 0:
                logger.info("WebSocket 认证成功")
                self.running = True
                self.reconnect_delay = self.RECONNECT_DELAY  # 重置重连延迟
                return True
            else:
                error_msg = resp_data.get("msg", "未知错误")
                logger.error(f"WebSocket 认证失败: {error_msg}")
                await self.disconnect()
                return False
                
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}", exc_info=True)
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.running = False
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
            self.ws = None
        logger.info("WebSocket 已断开")
    
    async def send_heartbeat(self):
        """发送心跳"""
        if not self.ws or not self.running:
            return
        
        try:
            heartbeat_msg = {
                "cmd": "heartbeat",
                "req_id": self._get_req_id()
            }
            await self.ws.send(json.dumps(heartbeat_msg))
            logger.debug("已发送心跳")
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
    
    async def send_message(self, to: str, content: str, msg_type: str = "text") -> bool:
        """
        发送消息
        
        Args:
            to: 接收者 (用户ID或群ID)
            content: 消息内容
            msg_type: 消息类型 (text/markdown)
        
        Returns:
            True 如果发送成功
        """
        if not self.ws or not self.running:
            logger.error("WebSocket 未连接")
            return False
        
        try:
            msg = {
                "cmd": "send",
                "req_id": self._get_req_id(),
                "data": {
                    "to": to,
                    "msgtype": msg_type,
                    msg_type: {
                        "content": content
                    }
                }
            }
            
            await self.ws.send(json.dumps(msg))
            logger.info(f"已发送消息: to={to}, type={msg_type}")
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            return False
    
    async def handle_message(self, data: Dict[str, Any]):
        """
        处理接收到的消息
        
        Args:
            data: 消息数据
        """
        cmd = data.get("cmd")
        
        if cmd == "heartbeat":
            # 心跳响应
            logger.debug("收到心跳响应")
            return
        
        if cmd == "callback":
            # 消息回调
            msg_data = data.get("data", {})
            msg_type = msg_data.get("msgtype")
            
            logger.info(f"收到消息: msgtype={msg_type}")
            
            if self.on_message:
                try:
                    await self.on_message(msg_data)
                except Exception as e:
                    logger.error(f"消息回调处理失败: {e}", exc_info=True)
    
    async def receive_loop(self):
        """接收消息循环"""
        while self.running and self.ws:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                await self.handle_message(data)
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket 连接已关闭")
                break
            except Exception as e:
                logger.error(f"接收消息失败: {e}", exc_info=True)
                break
    
    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            await asyncio.sleep(self.heartbeat_interval)
            if self.running:
                await self.send_heartbeat()
    
    async def run(self):
        """运行客户端"""
        while True:
            # 连接
            if await self.connect():
                # 启动接收和心跳任务
                try:
                    await asyncio.gather(
                        self.receive_loop(),
                        self.heartbeat_loop()
                    )
                except Exception as e:
                    logger.error(f"运行异常: {e}", exc_info=True)
            
            # 如果还在运行，则重连
            if self.running:
                logger.info(f"{self.reconnect_delay}秒后重连...")
                await asyncio.sleep(self.reconnect_delay)
                
                # 指数退避
                self.reconnect_delay = min(
                    self.reconnect_delay * 2,
                    self.MAX_RECONNECT_DELAY
                )
            else:
                break
    
    async def start(self):
        """启动客户端"""
        self.running = True
        await self.run()
    
    async def stop(self):
        """停止客户端"""
        self.running = False
        await self.disconnect()
