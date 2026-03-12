"""
Cron Scheduler for AI Life OS.

基于 asyncio 的轻量级定时任务调度器。
支持 cron 表达式,无需额外依赖。
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

logger = logging.getLogger("cron_scheduler")

# 配置文件路径
SCHEDULER_DIR = Path(__file__).parent
CRON_CONFIG_PATH = SCHEDULER_DIR / "cron_config.yaml"


@dataclass
class CronJob:
    """定时任务数据模型。"""
    name: str
    cron_expr: str
    handler: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    def __post_init__(self):
        """初始化时计算下次运行时间。"""
        if self.enabled:
            self.next_run = self._calculate_next_run()

    def _parse_cron(self) -> tuple:
        """
        解析 cron 表达式。

        格式: "分 时 日 月 周"
        例如: "0 21 * * *" 表示每天 21:00

        Returns:
            (minute, hour, day, month, weekday)
        """
        parts = self.cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {self.cron_expr}")

        def parse_part(part: str) -> Optional[int]:
            """解析单个部分,* 表示任意值。"""
            if part == "*":
                return None
            return int(part)

        return (
            parse_part(parts[0]),  # minute
            parse_part(parts[1]),  # hour
            parse_part(parts[2]),  # day
            parse_part(parts[3]),  # month
            parse_part(parts[4]),  # weekday
        )

    def _calculate_next_run(self, from_time: Optional[datetime] = None) -> datetime:
        """
        计算下次运行时间。

        Args:
            from_time: 起始时间,默认为当前时间

        Returns:
            下次运行时间
        """
        if from_time is None:
            from_time = datetime.now()

        minute, hour, day, month, weekday = self._parse_cron()

        # 从下一分钟开始检查
        next_time = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # 最多检查 366 天
        for _ in range(366 * 24 * 60):
            # 检查是否匹配所有条件
            if minute is not None and next_time.minute != minute:
                next_time += timedelta(minutes=1)
                continue
            if hour is not None and next_time.hour != hour:
                next_time += timedelta(hours=1)
                continue
            if day is not None and next_time.day != day:
                next_time += timedelta(days=1)
                continue
            if month is not None and next_time.month != month:
                # 跳到下个月
                if next_time.month == 12:
                    next_time = next_time.replace(year=next_time.year + 1, month=1, day=1)
                else:
                    next_time = next_time.replace(month=next_time.month + 1, day=1)
                continue
            if weekday is not None and next_time.weekday() != weekday:
                next_time += timedelta(days=1)
                continue

            # 所有条件都匹配
            return next_time

        # 如果一年内都找不到,返回一个未来时间
        return from_time + timedelta(days=365)

    def should_run(self, now: Optional[datetime] = None) -> bool:
        """
        检查是否应该运行。

        Args:
            now: 当前时间,默认为 datetime.now()

        Returns:
            是否应该运行
        """
        if not self.enabled:
            return False

        if now is None:
            now = datetime.now()

        # 检查是否到达下次运行时间
        if self.next_run and now >= self.next_run:
            return True

        return False

    def mark_run(self, now: Optional[datetime] = None):
        """
        标记任务已运行,更新下次运行时间。

        Args:
            now: 当前时间,默认为 datetime.now()
        """
        if now is None:
            now = datetime.now()

        self.last_run = now
        self.next_run = self._calculate_next_run(now)


class CronScheduler:
    """定时任务调度器。"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CRON_CONFIG_PATH
        self.jobs: Dict[str, CronJob] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def register_job(self, job: CronJob) -> None:
        """
        注册定时任务。

        Args:
            job: CronJob 实例
        """
        self.jobs[job.name] = job
        logger.info(f"[CronScheduler] 已注册任务: {job.name} (cron: {job.cron_expr}, enabled: {job.enabled})")

    def unregister_job(self, name: str) -> None:
        """
        取消注册定时任务。

        Args:
            name: 任务名称
        """
        if name in self.jobs:
            del self.jobs[name]
            logger.info(f"[CronScheduler] 已取消任务: {name}")

    def start(self) -> None:
        """启动调度器。"""
        if self.running:
            logger.warning("[CronScheduler] 调度器已在运行")
            return

        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[CronScheduler] 调度器已启动,共 {len(self.jobs)} 个任务")

    def stop(self) -> None:
        """停止调度器。"""
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[CronScheduler] 调度器已停止")

    def load_config(self) -> None:
        """从配置文件加载任务。"""
        if not self.config_path.exists():
            logger.warning(f"[CronScheduler] 配置文件不存在: {self.config_path}")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            jobs_config = config.get("jobs", [])
            for job_config in jobs_config:
                name = job_config.get("name")
                cron_expr = job_config.get("cron")
                enabled = job_config.get("enabled", True)

                if not name or not cron_expr:
                    logger.warning(f"[CronScheduler] 跳过无效配置: {job_config}")
                    continue

                # 获取对应的 handler
                handler = self._get_handler(name)
                if handler:
                    job = CronJob(
                        name=name,
                        cron_expr=cron_expr,
                        handler=handler,
                        enabled=enabled
                    )
                    self.register_job(job)

            logger.info(f"[CronScheduler] 已从配置文件加载 {len(self.jobs)} 个任务")

        except Exception as e:
            logger.error(f"[CronScheduler] 加载配置文件失败: {e}")

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _get_handler(self, name: str) -> Optional[Callable]:
        """
        根据任务名称获取处理函数。

        Args:
            name: 任务名称

        Returns:
            处理函数或 None
        """
        handlers = {
            "daily-retrospective": self._daily_retrospective_handler,
            "weekly-retrospective": self._weekly_retrospective_handler,
        }
        return handlers.get(name)

    async def _run_loop(self) -> None:
        """主循环,每分钟检查一次。"""
        while self.running:
            try:
                now = datetime.now()

                # 检查每个任务
                for job in self.jobs.values():
                    if job.should_run(now):
                        try:
                            logger.info(f"[CronScheduler] 执行任务: {job.name}")
                            # 异步执行任务
                            if asyncio.iscoroutinefunction(job.handler):
                                await job.handler()
                            else:
                                # 在线程池中执行同步函数
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, job.handler)

                            # 标记任务已运行
                            job.mark_run(now)

                        except Exception as e:
                            logger.error(f"[CronScheduler] 任务执行失败 {job.name}: {e}")

                # 每分钟检查一次
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CronScheduler] 调度循环错误: {e}")
                await asyncio.sleep(60)

    # ------------------------------------------------------------------ #
    # 任务处理函数
    # ------------------------------------------------------------------ #

    def _daily_retrospective_handler(self) -> None:
        """每日复盘任务处理函数。"""
        try:
            from core.retrospective import generate_guardian_retrospective

            logger.info("[CronScheduler] 开始执行每日复盘...")
            result = generate_guardian_retrospective(days=1)

            # 发送 Telegram 通知
            self._send_telegram_notification(
                title="📊 每日复盘",
                content=self._format_retrospective_message(result, days=1)
            )

            logger.info("[CronScheduler] 每日复盘完成")

        except Exception as e:
            logger.error(f"[CronScheduler] 每日复盘失败: {e}")

    def _weekly_retrospective_handler(self) -> None:
        """每周复盘任务处理函数。"""
        try:
            from core.retrospective import generate_guardian_retrospective

            logger.info("[CronScheduler] 开始执行每周复盘...")
            result = generate_guardian_retrospective(days=7)

            # 发送 Telegram 通知
            self._send_telegram_notification(
                title="📈 每周复盘",
                content=self._format_retrospective_message(result, days=7)
            )

            logger.info("[CronScheduler] 每周复盘完成")

        except Exception as e:
            logger.error(f"[CronScheduler] 每周复盘失败: {e}")

    def _send_telegram_notification(self, title: str, content: str) -> None:
        """
        发送 Telegram 通知。

        Args:
            title: 标题
            content: 内容
        """
        try:
            # 检查 Telegram 是否启用
            if not self._is_telegram_enabled():
                logger.info(f"[CronScheduler] Telegram 未启用,仅记录日志: {title}")
                logger.info(f"[CronScheduler] 内容: {content[:200]}...")
                return

            from interface.notifiers.telegram_notifier import TelegramNotifier
            from interface.notifiers.base import Notification, NotificationPriority
            from core.telegram_config import get_telegram_config

            cfg = get_telegram_config()
            notifier = TelegramNotifier({
                "bot_token": cfg.get("bot_token", ""),
                "chat_id": cfg.get("chat_id", ""),
                "enabled": True,
            })

            notification = Notification(
                title=title,
                message=content,
                priority=NotificationPriority.NORMAL,
            )

            success = notifier.send(notification)
            if success:
                logger.info(f"[CronScheduler] Telegram 通知已发送: {title}")
            else:
                logger.warning(f"[CronScheduler] Telegram 通知发送失败: {title}")

        except Exception as e:
            logger.error(f"[CronScheduler] 发送 Telegram 通知失败: {e}")

    def _is_telegram_enabled(self) -> bool:
        """检查 Telegram 是否启用。"""
        try:
            if not self.config_path.exists():
                return False

            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            return config.get("telegram", {}).get("enabled", False)

        except Exception:
            return False

    def _format_retrospective_message(self, result: Dict[str, Any], days: int) -> str:
        """
        格式化复盘消息。

        Args:
            result: 复盘结果
            days: 天数

        Returns:
            格式化后的消息
        """
        period = result.get("period", {})
        observations = result.get("observations", [])

        lines = [
            f"时间范围: {period.get('start_date')} ~ {period.get('end_date')}",
            "",
            "观察:",
        ]

        for obs in observations[:3]:
            lines.append(f"• {obs}")

        # 添加偏差信号
        deviation_signals = result.get("deviation_signals", [])
        active_signals = [s for s in deviation_signals if s.get("active")]
        if active_signals:
            lines.append("")
            lines.append("⚠️ 偏差信号:")
            for signal in active_signals[:2]:
                lines.append(f"• {signal.get('name')}: {signal.get('summary', '')}")

        return "\n".join(lines)


# 单例实例
_scheduler_instance: Optional[CronScheduler] = None


def get_scheduler() -> CronScheduler:
    """获取 CronScheduler 单例实例。"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CronScheduler()
    return _scheduler_instance
