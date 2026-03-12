"""
Telegram Configuration for AI Life OS.

提供 Telegram Bot 配置读取接口。
支持从 config/system.yaml 和环境变量读取配置。
"""
import os
from pathlib import Path
from typing import Dict, Any

import yaml

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
SYSTEM_CONFIG_PATH = CONFIG_DIR / "system.yaml"


def get_telegram_config() -> Dict[str, Any]:
    """
    获取 Telegram 配置。

    优先级：环境变量 > config/system.yaml

    Returns:
        包含 bot_token, chat_id 的字典
    """
    config = {
        "bot_token": "",
        "chat_id": "",
    }

    # 1. 从 system.yaml 读取
    if SYSTEM_CONFIG_PATH.exists():
        try:
            with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as f:
                system_config = yaml.safe_load(f) or {}

            telegram_config = system_config.get("telegram", {})
            if isinstance(telegram_config, dict):
                config["bot_token"] = telegram_config.get("bot_token", "")
                config["chat_id"] = telegram_config.get("chat_id", "")

        except Exception as e:
            print(f"[TelegramConfig] 读取配置文件失败: {e}")

    # 2. 环境变量覆盖
    env_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_bot_token:
        config["bot_token"] = env_bot_token

    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if env_chat_id:
        config["chat_id"] = env_chat_id

    return config


def is_telegram_configured() -> bool:
    """
    检查 Telegram 是否已配置。

    Returns:
        bot_token 和 chat_id 是否都不为空
    """
    config = get_telegram_config()
    return bool(config.get("bot_token")) and bool(config.get("chat_id"))
