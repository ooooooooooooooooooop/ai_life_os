"""
Blueprint Goal Engine - 目标驱动内核

核心原则：
- 无硬编码目标，从 Blueprint 动态提取
- 三维框架（Wisdom/Experience/Connection）作为理解模型
- 自适应进度追踪和不安触发
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import re

from core.llm_adapter import get_llm
from core.blueprint_anchor import AnchorManager, BlueprintAnchor


class GoalDimension(Enum):
    """
    目标维度（理解模型，非硬编码）
    
    这三个维度来自 better_human_blueprint，
    作为系统理解目标时的分类框架，
    但不限制用户表达。
    """
    WISDOM = "wisdom"           # 认知深度：思想连接、知识积累、创作产出
    EXPERIENCE = "experience"   # 体验强度：心流状态、感官在场、深度投入
    CONNECTION = "connection"   # 连接质量：深度对话、有意义的关系、利他行为
    OTHER = "other"             # 其他维度（用户自定义）


class GoalPattern(Enum):
    """
    目标模式（理解模型，非硬编码）
    
    系统识别目标时使用的四种模式，
    帮助判断如何追踪进度。
    """
    GROWTH = "growth"           # 需要持续增长的 (如: 知识、技能)
    FREQUENCY = "frequency"     # 需要保持频率的 (如: 某种行为)
    DURATION = "duration"       # 需要保持时长的 (如: 专注时间)
    MILESTONE = "milestone"     # 需要达成阶段的 (如: 项目交付)


class ProgressStatus(Enum):
    """进度状态"""
    ON_TRACK = "on_track"       # 正常推进
    PROGRESSING = "progressing" # 有进展但低于预期
    STAGNANT = "stagnant"       # 停滞（应触发不安）
    DECLINING = "declining"     # 倒退（应主动干预）
    UNKNOWN = "unknown"         # 无法判断


@dataclass
class Goal:
    """
    动态提取的目标
    
    所有字段都从 Blueprint/Anchor 提取，
    不硬编码任何具体值。
    """
    id: str
    title: str
    description: str
    dimension: GoalDimension
    pattern: GoalPattern
    source_commitment: str  # 对应 Anchor 中的 long_horizon_commitment
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "dimension": self.dimension.value,
            "pattern": self.pattern.value,
            "source_commitment": self.source_commitment
        }


@dataclass
class ProgressAssessment:
    """进度评估结果"""
    goal_id: str
    status: ProgressStatus
    confidence: float  # 0-1
    explanation: str
    last_progress_date: Optional[str] = None
    days_since_progress: Optional[int] = None


@dataclass
class Alert:
    """不安警报"""
    level: str  # "GOAL_ANXIETY" | "ANTI_VALUE_DRIFT" | "INSTINCT_HIJACK"
    representing: str  # "BLUEPRINT_SELF"
    goal_id: Optional[str]
    message: str
    suggestion: Optional[str] = None
    
    OK: "Alert" = None  # 无警报的占位符

# 初始化 OK 占位符
Alert.OK = None


class GoalExtractor:
    """
    从 Blueprint + Anchor 提取目标
    
    使用 LLM 理解 Anchor 中的 long_horizon_commitments，
    将其转换为结构化的 Goal 对象。
    """
    
    ANALYSIS_PROMPT = """分析以下长期承诺，判断其维度和模式。

承诺内容：
"{commitment}"

请判断：
1. 维度 (dimension): wisdom（认知）| experience（体验）| connection（连接）| other
2. 模式 (pattern): growth（增长）| frequency（频率）| duration（时长）| milestone（里程碑）

请输出 JSON 格式：
```json
{{
  "title": "简短标题（10字以内）",
  "description": "承诺的核心含义",
  "dimension": "wisdom|experience|connection|other",
  "pattern": "growth|frequency|duration|milestone"
}}
```

只输出 JSON，不要其他解释。"""
    
    def extract(self, anchor: BlueprintAnchor) -> List[Goal]:
        """
        从 Anchor 的 long_horizon_commitments 提取目标
        
        Args:
            anchor: 当前激活的 Anchor
            
        Returns:
            提取的目标列表
        """
        goals = []
        
        for i, commitment in enumerate(anchor.long_horizon_commitments):
            goal_info = self._analyze_commitment(commitment)
            
            # 解析维度
            dimension_str = goal_info.get("dimension", "other")
            try:
                dimension = GoalDimension(dimension_str)
            except ValueError:
                dimension = GoalDimension.OTHER
            
            # 解析模式
            pattern_str = goal_info.get("pattern", "growth")
            try:
                pattern = GoalPattern(pattern_str)
            except ValueError:
                pattern = GoalPattern.GROWTH
            
            goals.append(Goal(
                id=f"goal_{i+1}",
                title=goal_info.get("title", commitment[:20]),
                description=goal_info.get("description", commitment),
                dimension=dimension,
                pattern=pattern,
                source_commitment=commitment
            ))
        
        return goals
    
    def _analyze_commitment(self, commitment: str) -> Dict[str, str]:
        """使用 LLM 分析单个承诺"""
        llm = get_llm()
        
        response = llm.generate(
            prompt=self.ANALYSIS_PROMPT.format(commitment=commitment),
            temperature=0.0  # ANCHOR_EXTRACTION 模式
        )
        
        # 解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', response.content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 解析失败时返回默认值
        return {
            "title": commitment[:20],
            "description": commitment,
            "dimension": "other",
            "pattern": "growth"
        }


class AdaptiveAnxiety:
    """
    自适应不安触发
    
    根据目标的自然节奏判断是否应该触发"不安"警报，
    不硬编码具体阈值。
    """
    
    ANXIETY_PROMPT = """判断以下目标是否应该触发"不安"警报。

目标信息：
- 标题: {title}
- 描述: {description}
- 模式: {pattern}
- 距离上次进展: {days_since_progress} 天

判断标准（根据目标模式）：
- growth: 知识/技能类，通常月度检查
- frequency: 行为习惯类，通常周度检查
- duration: 时间投入类，通常日度检查
- milestone: 项目交付类，通常季度检查

请判断：
1. 是否应该触发不安警报？
2. 理由是什么？
3. 有什么建议？

请输出 JSON：
```json
{{
  "should_trigger": true|false,
  "reason": "理由",
  "suggestion": "建议"
}}
```"""
    
    def check(self, goal: Goal, days_since_progress: int) -> Optional[Alert]:
        """
        检查目标是否应该触发不安警报
        
        Args:
            goal: 目标
            days_since_progress: 距离上次进展的天数
            
        Returns:
            警报对象，如果无需警报返回 None
        """
        llm = get_llm()
        
        response = llm.generate(
            prompt=self.ANXIETY_PROMPT.format(
                title=goal.title,
                description=goal.description,
                pattern=goal.pattern.value,
                days_since_progress=days_since_progress
            ),
            temperature=0.0
        )
        
        # 解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', response.content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                
                if result.get("should_trigger", False):
                    return Alert(
                        level="GOAL_ANXIETY",
                        representing="BLUEPRINT_SELF",
                        goal_id=goal.id,
                        message=f"⚠️ 目标「{goal.title}」已停滞 {days_since_progress} 天。{result.get('reason', '')}",
                        suggestion=result.get("suggestion")
                    )
            except json.JSONDecodeError:
                pass
        
        return None


class GoalEngine:
    """
    目标引擎主类
    
    职责：
    - 从 Anchor 提取目标
    - 追踪目标进度
    - 触发不安警报
    """
    
    def __init__(self):
        self.anchor_manager = AnchorManager()
        self.extractor = GoalExtractor()
        self.anxiety = AdaptiveAnxiety()
        self._goals: List[Goal] = []
        self._anchor_version: Optional[str] = None
    
    def refresh(self):
        """刷新目标（从当前 Anchor 重新提取）"""
        anchor = self.anchor_manager.get_current()
        if anchor:
            # 只在 Anchor 版本变化时重新提取
            if self._anchor_version != anchor.version:
                self._goals = self.extractor.extract(anchor)
                self._anchor_version = anchor.version
    
    def get_goals(self) -> List[Goal]:
        """获取所有目标"""
        if not self._goals:
            self.refresh()
        return self._goals
    
    def get_by_dimension(self, dimension: GoalDimension) -> List[Goal]:
        """按维度获取目标"""
        return [g for g in self.get_goals() if g.dimension == dimension]
    
    def get_by_pattern(self, pattern: GoalPattern) -> List[Goal]:
        """按模式获取目标"""
        return [g for g in self.get_goals() if g.pattern == pattern]
    
    def check_all_anxieties(self, days_since_progress: int = 7) -> List[Alert]:
        """
        检查所有目标的不安状态
        
        Args:
            days_since_progress: 假设的停滞天数（实际应从进度记录获取）
            
        Returns:
            所有触发的警报列表
        """
        alerts = []
        
        for goal in self.get_goals():
            alert = self.anxiety.check(goal, days_since_progress)
            if alert:
                alerts.append(alert)
        
        return alerts
    
    def get_anchor(self) -> Optional[BlueprintAnchor]:
        """获取当前 Anchor"""
        return self.anchor_manager.get_current()
