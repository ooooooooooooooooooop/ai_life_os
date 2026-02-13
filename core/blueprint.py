"""
Blueprint Engine for AI Life OS.
Implements the decision rules, value function, and filtering logic.
"""
import yaml
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from core.models import Goal, UserProfile

from core.llm_adapter import get_llm


@dataclass
class BlueprintScore:
    passed: bool
    score: float
    breakdown: Dict[str, float]
    reason: str = ""

class Blueprint:
    """Blueprint 评估引擎"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default path: project_root/config/blueprint.yaml
            config_path = Path(__file__).parent.parent / "config" / "blueprint.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.threshold = self.config.get("threshold", 0.6)
        self.principles = self.config.get("principles", [])

    def _load_config(self) -> Dict:
        if not self.config_path.exists():
            # Fallback default config if file missing
            return {
                "threshold": 0.6,
                "principles": []
            }
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def evaluate(
        self,
        goal: Goal,
        context: UserProfile,
        mock_llm_response: Dict = None,
    ) -> BlueprintScore:
        """
        评估单个目标。
        mock_llm_response: 用于测试或避免真实 LLM 调用
        """
        # 1. 硬规则检查 (Hard Rules)
        hard_passed, reason = self._check_hard_rules(goal, context)
        if not hard_passed:
            return BlueprintScore(passed=False, score=0.0, breakdown={}, reason=reason)

        # 2. 软评分 (Soft Scoring)
        scores = {}

        if mock_llm_response:
             scores = mock_llm_response
        else:
            scores = self._evaluate_with_llm(goal, context)

        # 3. 加权平均
        total_score = self._weighted_average(scores)

        return BlueprintScore(
            passed=total_score >= self.threshold,
            score=total_score,
            breakdown=scores,
            reason="Passed" if total_score >= self.threshold else "Score too low"
        )

    def _evaluate_with_llm(self, goal: Goal, context: UserProfile) -> Dict[str, float]:
        """使用 LLM 对目标进行多维度评分"""
        llm = get_llm()

        principles_text = "\n".join(
            [f"- {p['name']}: {p.get('description', '')}" for p in self.principles]
        )

        prompt = f"""
        Evaluate the following goal based on the "Better Human Blueprint" principles.

        Principles:
        {principles_text}

        User Context:
        Occupation: {context.occupation}
        Focus Area: {context.focus_area}
        Preferences: {context.preferences}

        Goal to Evaluate:
        Title: {goal.title}
        Description: {goal.description}
        Target Level: {goal.target_level}

        Task:
        Rate this goal on a scale of 0.0 to 1.0 for EACH principle above.

        CRITICAL SCORING GUIDELINES:
        - **0.0 - 0.4**: Poor fit. Generic, vague, or irrelevant.
        - **0.5 - 0.7**: Average. Acceptable but not exciting.
        - **0.8 - 0.9**: Excellent. Highly tailored and impactful.
        - **1.0**: Perfect. A life-changing goal.
        - **Do NOT** give high scores (0.8+) easily. Be strict.
        - Differentiation is key. If a goal is boring, give it a low `joy_factor`.

        Return ONLY a JSON object mapping principle names to scores.
        Example:
        {{
            "life_value": 0.8,
            "growth_potential": 0.9,
            "feasibility": 0.5,
            "joy_factor": 0.7
        }}
        """

        try:
            response = llm.generate(prompt)
            # 简单的 JSON 提取逻辑
            content = response.content
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                return {p["name"]: 0.5 for p in self.principles} # Fallback
        except Exception as e:
            print(f"Error evaluating goal {goal.title}: {e}")
            return {p["name"]: 0.5 for p in self.principles}

    def filter_and_rank(
        self,
        goals: List[Goal],
        context: UserProfile,
    ) -> List[Tuple[Goal, BlueprintScore]]:
        """
        过滤并排序候选目标。
        返回 [(Goal, Score), ...]
        """
        results = []
        for goal in goals:
            # 使用真实评估与 LLM
            score = self.evaluate(goal, context)
            if score.passed:
                results.append((goal, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1].score, reverse=True)
        return results

    def _check_hard_rules(self, goal: Goal, context: UserProfile) -> Tuple[bool, str]:
        """检查硬规则"""

        # 规则 1: 预算时间检查
        # 简单解析 daily_hours (e.g., "3h")
        try:
            daily_limit = float(context.daily_hours.lower().replace("h", ""))
        except (AttributeError, TypeError, ValueError):
            daily_limit = 2.0  # default

        # 假设 goal.resource_description 包含预估时间，这里暂时简化
        # 实际应从 Goal 对象结构化数据中取
        estimated_hours = 1.0 # 默认

        if estimated_hours > daily_limit * 1.5:
            return (
                False,
                "Estimated time "
                f"({estimated_hours}h) exceeds daily limit ({daily_limit}h * 1.5)",
            )

        return True, ""

    def _weighted_average(self, scores: Dict[str, float]) -> float:
        """计算加权平均分"""
        total_weight = 0.0
        weighted_sum = 0.0

        weight_map = {p["name"]: p["weight"] for p in self.principles}

        for name, score in scores.items():
            weight = weight_map.get(name, 0.0)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight
