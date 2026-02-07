"""
Configuration Manager for AI Life OS.

集中管理系统常量和配置参数。
遵循 RIPER Rule 2：所有经验值必须显式声明并可配置。

使用方式:
    from core.config_manager import config
    limit = config.DAILY_TASK_LIMIT
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


CONFIG_DIR = Path(__file__).parent.parent / "config"
RUNTIME_CONFIG_PATH = CONFIG_DIR / "runtime.yaml"


@dataclass
class SystemConfig:
    """
    系统运行时常量配置。
    
    所有值均为经验值，可根据用户实际情况调整。
    调整建议已在注释中说明。
    """
    
    # === 时间与调度 ===
    
    # 周报触发日 (0=周一, 6=周日)
    # 经验值依据：周日通常是反思和规划的最佳时机
    # 调整建议：根据用户工作节律调整，如偏好周五可设为 4
    WEEKLY_REVIEW_DAY: int = 6
    
    # === 规划器参数 ===
    
    # 每日任务上限
    # 经验值依据：认知负荷理论，5±2 法则
    # 调整建议：精力充沛者可增至 7，疲劳期可降至 3
    DAILY_TASK_LIMIT: int = 5
    
    # 事件回溯窗口（用于习惯分析）
    # 经验值依据：50 条约覆盖 1-2 周的典型使用
    # 调整建议：活跃用户可增至 100，新用户保持 50
    EVENT_LOOKBACK: int = 50
    
    # 习惯行动上限（每日）
    # 经验值依据：避免过多习惯占用探索空间
    # 调整建议：稳定期可增至 4-5
    MAX_RHYTHM_ACTIONS: int = 3
    
    # 探索行动上限（每日）
    # 经验值依据：保持可管理的新任务数量
    # 调整建议：冒险期可增至 3
    MAX_EXPLORATION_ACTIONS: int = 2
    
    # === 快照与维护 ===
    
    # 快照保留天数
    # 经验值依据：30 天足以回溯大多数问题
    # 调整建议：存储紧张可降至 14
    SNAPSHOT_RETENTION_DAYS: int = 30
    
    # === 任务粒度参数 ===
    
    # 最小任务时间块 (分钟)
    # 经验值依据：番茄工作法 (25min + 5min break) 及认知切换成本
    # 调整建议：注意力集中困难者可降至 15，深度工作者可增至 60
    MIN_TASK_DURATION: int = 25

    # 习惯分析温度（低温更保守）
    # 经验值依据：习惯应稳定，低温减少随机性
    RHYTHM_ANALYSIS_TEMPERATURE: float = 0.3
    
    # 探索建议温度（高温更有创意）
    # 经验值依据：探索需要多样性
    EXPLORATION_TEMPERATURE: float = 0.7
    
    # === 节律分析参数 ===
    
    # 习惯分析最小事件数
    # 经验值依据：少于 5 条事件无法识别有意义的模式
    # 调整建议：数据丰富后可增至 10
    MIN_EVENTS_FOR_RHYTHM: int = 5
    
    # 默认精力阶段 (时间不在任何区间时)
    # 经验值依据：休闲是最宽松的阶段，适合作为 fallback
    # 调整建议：可根据用户偏好改为其他阶段
    DEFAULT_ENERGY_PHASE: str = "leisure"
    
    # 默认学习日志路径
    # 经验值依据：常见的笔记目录结构
    # 调整建议：根据用户实际笔记系统调整
    DEFAULT_LOG_PATH: str = "notes/learning-log.md"
    
    # === 精力节律 (Energy Rhythm) ===
    # 定义每天的精力阶段及其适用任务类型
    ENERGY_PHASES: dict = None
    
    # === 节律分析参数 ===
    
    # 习惯判定最小次数
    # 经验值依据：少于 2 次难以判定为重复行为，3 次开始形成模式
    # 调整建议：数据丰富后可增至 5
    HABIT_MIN_OCCURRENCES: int = 3
    
    # 成功率阈值（用于判定习惯是否稳定）
    # 经验值依据：60% 以上表示用户倾向于完成该任务
    # 调整建议：严格用户可提高至 0.75
    HABIT_SUCCESS_RATE_THRESHOLD: float = 0.6
    
    # 样本量最小值（用于计算成功率）
    # 经验值依据：少于 2 次的统计不可靠
    # 调整建议：可保持不变
    STATS_MIN_SAMPLE_SIZE: int = 2

    def __post_init__(self):
        if self.ENERGY_PHASES is None:
            self.ENERGY_PHASES = {
                "06:00-09:00": "activation",   # 唤醒: 无输入，身体活动
                "09:00-13:00": "deep_work",    # 深度工作: L2 Only, 屏蔽干扰
                "13:00-14:00": "connection",   # 连接: 社交午餐
                "14:00-18:00": "logistics",    # 物流: L1 批处理
                "18:00-22:00": "leisure"       # 休闲: 艺术/娱乐 (无逻辑)
            }


def _load_runtime_config() -> dict:
    """加载运行时配置覆盖（如果存在）。"""
    if not RUNTIME_CONFIG_PATH.exists():
        return {}
    
    try:
        with open(RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def get_config() -> SystemConfig:
    """
    获取系统配置实例。
    
    优先级：runtime.yaml > 默认值
    """
    base = SystemConfig()
    overrides = _load_runtime_config()
    
    for key, value in overrides.items():
        if hasattr(base, key):
            setattr(base, key, value)
    
    return base


# 全局配置实例（单例模式）
config = get_config()
