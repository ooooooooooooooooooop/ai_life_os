from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import re

BHB_PATH = Path(__file__).parent.parent.parent / "docs/concepts/better_human_blueprint.md"


@dataclass
class LifeMetric:
    """单个生命指标"""
    name: str                    # 指标名称 (e.g., "flow_state_duration")
    description: str             # 描述
    unit: str                    # 单位 (e.g., "hours/day")
    target: Optional[float] = None  # 目标值 (如有)


@dataclass
class BHBConfig:
    """解析后的 BHB 配置"""
    philosophy: str              # 核心哲学 (单句)
    strategic_goals: List[str]   # 战略目标 (3个维度)
    life_metrics: List[LifeMetric]
    energy_phases: List[str]     # 精力阶段名称
    anti_patterns: List[str]     # 反模式 (痛苦来源)
    raw_text: str                # 原始文本 (供 LLM 参考)


def parse_bhb() -> BHBConfig:
    """
    解析 better_human_blueprint.md。
    
    解析策略:
    1. 正则提取结构化内容 (Goal, Life Metric)
    2. 保留原始 Markdown 供 LLM 深度理解
    """
    if not BHB_PATH.exists():
        return _empty_config()
    
    raw_text = BHB_PATH.read_text(encoding="utf-8")
    
    # 1. 提取核心哲学 (第一个引用块)
    philosophy_match = re.search(r'\*\*"(.+?)"\*\*', raw_text)
    philosophy = philosophy_match.group(1) if philosophy_match else ""
    
    # 2. 提取战略目标 (Goal 1/2/3)
    goals = re.findall(r'### Goal \d: (.+?)[\r\n]', raw_text)
    
    # 3. 提取 Life Metrics (Life Metric: 格式)
    metrics = []
    # 匹配 **Life Metric**: ... 或者 **Life Metric**: ... 
    # 这里的正则需要根据实际文件格式微调。假设格式为: **Life Metric**: **Flow State Duration**...
    metric_matches = re.findall(
        r'\*\*Life Metric\*\*[:\s]+\*?\*?([^*\n]+)', 
        raw_text
    )
    for m in metric_matches:
        # 尝试解析 "Flow State Duration (心流时长)" 格式
        # 简单处理：取括号前作为name
        name_str = m.strip()
        
        # 简单的 name extraction
        name_match = re.match(r'([^(]+)', name_str)
        if name_match:
            raw_name = name_match.group(1).strip()
            # 转换为 snake_case
            safe_name = raw_name.lower().replace(" ", "_")
            
            metrics.append(LifeMetric(
                name=safe_name,
                description=name_str,
                unit="count"  # 默认
            ))
    
    # 4. 提取精力阶段 (Phase N: Name)
    phases = re.findall(r'\*\*Phase \d: (\w+)', raw_text)
    
    # 5. 提取反模式 (痛苦来源)
    anti_patterns = []
    problem_matches = re.findall(r'\*\*The Problem\*\*[:\s]+(.+?)[\r\n]', raw_text)
    for p in problem_matches:
        anti_patterns.append(p.strip())
    
    return BHBConfig(
        philosophy=philosophy,
        strategic_goals=goals,
        life_metrics=metrics,
        energy_phases=phases,
        anti_patterns=anti_patterns,
        raw_text=raw_text
    )


def _empty_config() -> BHBConfig:
    """BHB 文件不存在时的空配置"""
    return BHBConfig(
        philosophy="",
        strategic_goals=[],
        life_metrics=[],
        energy_phases=[],
        anti_patterns=[],
        raw_text=""
    )
