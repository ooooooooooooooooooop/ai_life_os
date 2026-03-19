"""
企业微信消息加解密工具

参考 OpenClaw China 实现
"""
import hashlib
import base64
import struct
import os
from typing import Optional, Tuple
from Crypto.Cipher import AES


class WeComCrypto:
    """企业微信消息加解密"""
    
    BLOCK_SIZE = 32  # AES块大小
    
    def __init__(self, token: str, encoding_aes_key: str, receive_id: str = ""):
        """
        初始化加解密器
        
        Args:
            token: 消息令牌
            encoding_aes_key: 消息加密密钥
            receive_id: 接收方ID（企业ID或应用ID）
        """
        self.token = token
        self.encoding_aes_key = encoding_aes_key
        self.receive_id = receive_id
        
        # 解码AES密钥
        self.aes_key = self._decode_aes_key(encoding_aes_key)
        self.iv = self.aes_key[:16]
    
    def _decode_aes_key(self, encoding_aes_key: str) -> bytes:
        """解码AES密钥"""
        key_str = encoding_aes_key.strip()
        if not key_str:
            raise ValueError("encoding_aes_key不能为空")
        
        # 添加padding
        if not key_str.endswith("="):
            key_str += "="
        
        # Base64解码
        key = base64.b64decode(key_str)
        
        if len(key) != 32:
            raise ValueError(f"无效的encoding_aes_key，期望32字节，实际{len(key)}字节")
        
        return key
    
    def _pkcs7_pad(self, data: bytes) -> bytes:
        """PKCS7填充"""
        pad_len = self.BLOCK_SIZE - (len(data) % self.BLOCK_SIZE)
        return data + bytes([pad_len] * pad_len)
    
    def _pkcs7_unpad(self, data: bytes) -> bytes:
        """移除PKCS7填充"""
        if not data:
            raise ValueError("无效的PKCS7数据")
        
        pad_len = data[-1]
        if pad_len < 1 or pad_len > self.BLOCK_SIZE or pad_len > len(data):
            raise ValueError("无效的PKCS7填充")
        
        # 验证填充
        for i in range(1, pad_len + 1):
            if data[-i] != pad_len:
                raise ValueError("无效的PKCS7填充")
        
        return data[:-pad_len]
    
    def compute_signature(self, timestamp: str, nonce: str, encrypt: str) -> str:
        """
        计算消息签名
        
        Args:
            timestamp: 时间戳
            nonce: 随机数
            encrypt: 加密消息
        
        Returns:
            签名字符串
        """
        parts = [self.token, timestamp, nonce, encrypt]
        parts.sort()
        joined = "".join(parts)
        return hashlib.sha1(joined.encode()).hexdigest()
    
    def verify_signature(self, timestamp: str, nonce: str, encrypt: str, signature: str) -> bool:
        """
        验证消息签名
        
        Args:
            timestamp: 时间戳
            nonce: 随机数
            encrypt: 加密消息
            signature: 待验证的签名
        
        Returns:
            True 如果签名验证通过
        """
        expected = self.compute_signature(timestamp, nonce, encrypt)
        return expected == signature
    
    def decrypt(self, encrypt: str) -> str:
        """
        解密消息
        
        Args:
            encrypt: Base64编码的加密消息
        
        Returns:
            解密后的消息内容
        """
        # Base64解码
        encrypted_data = base64.b64decode(encrypt)
        
        # AES解密
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
        decrypted_padded = cipher.decrypt(encrypted_data)
        
        # 移除填充
        decrypted = self._pkcs7_unpad(decrypted_padded)
        
        if len(decrypted) < 20:
            raise ValueError(f"解密数据太短，期望至少20字节，实际{len(decrypted)}字节")
        
        # 解析消息结构
        # 格式: 16字节随机数 + 4字节消息长度 + 消息内容 + receive_id
        msg_len = struct.unpack(">I", decrypted[16:20])[0]
        msg_start = 20
        msg_end = msg_start + msg_len
        
        if msg_end > len(decrypted):
            raise ValueError(f"消息长度无效，msg_end={msg_end}, 数据长度={len(decrypted)}")
        
        msg = decrypted[msg_start:msg_end].decode('utf-8')
        
        # 验证receive_id
        if self.receive_id:
            trailing = decrypted[msg_end:].decode('utf-8')
            if trailing != self.receive_id:
                raise ValueError(f"receive_id不匹配，期望'{self.receive_id}'，实际'{trailing}'")
        
        return msg
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密消息
        
        Args:
            plaintext: 明文消息
        
        Returns:
            Base64编码的加密消息
        """
        # 生成16字节随机数
        random_16 = os.urandom(16)
        
        # 消息内容
        msg = plaintext.encode('utf-8')
        msg_len = struct.pack(">I", len(msg))
        receive_id = self.receive_id.encode('utf-8')
        
        # 组装数据
        raw = random_16 + msg_len + msg + receive_id
        
        # PKCS7填充
        padded = self._pkcs7_pad(raw)
        
        # AES加密
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
        encrypted = cipher.encrypt(padded)
        
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt_url(self, encrypt: str) -> Tuple[str, str]:
        """
        解密URL验证请求
        
        Args:
            encrypt: 加密的echostr参数
        
        Returns:
            (解密后的echostr, receive_id)
        """
        # Base64解码
        encrypted_data = base64.b64decode(encrypt)
        
        # AES解密
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
        decrypted_padded = cipher.decrypt(encrypted_data)
        
        # 移除填充
        decrypted = self._pkcs7_unpad(decrypted_padded)
        
        if len(decrypted) < 20:
            raise ValueError(f"解密数据太短")
        
        # 解析
        msg_len = struct.unpack(">I", decrypted[16:20])[0]
        msg_start = 20
        msg_end = msg_start + msg_len
        
        if msg_end > len(decrypted):
            raise ValueError(f"消息长度无效")
        
        echostr = decrypted[msg_start:msg_end].decode('utf-8')
        receive_id = decrypted[msg_end:].decode('utf-8')
        
        return echostr, receive_id
