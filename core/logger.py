"""
AI Life OS 日志配置模块。

配置日志策略：
- logs/system.log: 常规操作日志 (INFO+)
- logs/error.log: 异常堆栈 (ERROR/CRITICAL)
- console: 仅用户有用的提示 (WARNING+)

使用 RotatingFileHandler 防止日志文件过大。
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# 日志目录
LOGS_DIR = Path(__file__).parent.parent / "logs"

# 日志配置常量 (经验值，可根据需要调整)
MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 3  # 保留 3 个备份


def setup_logging(
    log_level: int = logging.INFO,
    console_level: int = logging.WARNING
) -> logging.Logger:
    """
    初始化日志系统。

    Args:
        log_level: 文件日志级别 (默认 INFO)
        console_level: 控制台日志级别 (默认 WARNING)

    Returns:
        配置好的 root logger
    """
    # 确保日志目录存在
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 获取 root logger
    logger = logging.getLogger("ai_life_os")
    logger.setLevel(logging.DEBUG)  # 捕获所有级别，由 handler 过滤

    # 清除现有 handlers (避免重复添加)
    logger.handlers.clear()

    # 日志格式
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_format = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )

    # 1. 系统日志 (INFO+)
    system_handler = RotatingFileHandler(
        LOGS_DIR / "system.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    system_handler.setLevel(log_level)
    system_handler.setFormatter(file_format)
    logger.addHandler(system_handler)

    # 2. 错误日志 (ERROR+)
    error_handler = RotatingFileHandler(
        LOGS_DIR / "error.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    logger.addHandler(error_handler)

    # 3. 控制台输出 (WARNING+)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取模块专用的 logger。

    Args:
        name: 模块名称，如 "planner", "llm_adapter"

    Returns:
        配置好的 logger 实例
    """
    if name:
        return logging.getLogger(f"ai_life_os.{name}")
    return logging.getLogger("ai_life_os")


def log_corruption(line_number: int, raw_line: str, error_msg: str) -> None:
    """
    记录数据损坏信息到专用日志。

    Args:
        line_number: 损坏行号
        raw_line: 原始行内容
        error_msg: 错误描述
    """
    corruption_log_path = LOGS_DIR / "corruption_dump.log"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    with open(corruption_log_path, "a", encoding="utf-8") as f:
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        f.write(f"[{timestamp}] Line {line_number}: {error_msg}\n")
        f.write(f"  Raw: {raw_line}\n")
        f.write("-" * 50 + "\n")

    # 同时记录 warning 到主日志
    logger = get_logger("event_sourcing")
    logger.warning(f"数据损坏 (行 {line_number}): {error_msg}")
