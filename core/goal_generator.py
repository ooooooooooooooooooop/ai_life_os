"""
Goal Generator for AI Life OS.
Generates candidate goals based on user profile and context using LLM.
Integrates user's "Blueprint" to filter and rank goals.
"""
import json
import logging
from typing import List, Dict, Tuple
from core.models import Goal, UserProfile, GoalStatus
from core.llm_adapter import get_llm
from core.blueprint import Blueprint

logger = logging.getLogger("goal_generator")

class GoalGenerator:
    """目标生成器"""

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint
        # Use complex model for goal generation as it requires reasoning
        self.llm = get_llm() # defaults to active_profile

    def generate_candidates(self, profile: UserProfile, n: int = 3) -> List[Tuple[Goal, Dict]]:
        """
        生成候选目标列表，并经过 Blueprint 评分。

        Returns:
            List of (Goal, BlueprintScore) sorted by score.
        """
        logger.info("Generating candidate goals...")

        prompt = self._build_prompt(profile, n)

        try:
            response = self.llm.generate(prompt)
            if not response.success:
                logger.error(f"LLM generation failed: {response.error}")
                return []

            raw_goals = self._parse_response(response.content)

            candidates = []
            for item in raw_goals:
                goal = Goal(
                    id=f"gen_{item.get('id', 'unknown')}",
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    source="ai_generated",
                    status=GoalStatus.PENDING_CONFIRM,
                    resource_description=item.get("resource_description", ""),
                    target_level=item.get("target_level", ""),
                    tags=item.get("tags", [])
                )
                candidates.append(goal)

            # Blueprint Filtering & Ranking
            ranked_results = self.blueprint.filter_and_rank(candidates, profile)

            return ranked_results

        except Exception as e:
            logger.error(f"Goal generation failed: {e}", exc_info=True)
            return []

    def _build_prompt(self, profile: UserProfile, n: int) -> str:
        """构建 Prompt"""

        import random
        random_seed = f"RandomSeed: {random.randint(1000, 9999)}"

        context_str = f"""
        User Profile:
        - Occupation: {profile.occupation}
        - Focus Area: {profile.focus_area}
        - Daily Available Time: {profile.daily_hours}
        - Preferences: {profile.preferences if profile.preferences else "None"}
        - Context: {random_seed}
        """

        return f"""
        You are an advanced AI Life Coach designed to help the user achieve
        a HOLISTIC, balanced, and self-actualized life.

        USER PROFILE:
        {context_str}

        CRITICAL INSTRUCTION:
        You MUST generate exactly 3 candidate goals, one for each of the following categories:
        1. **Career/Growth**: A hard skill or professional achievement related
           to their occupation. (The "Game Changer")
        2. **Health/Vitality**: A goal focused on physical or mental well-being
           (e.g., sleep, exercise, diet, meditation).
        3. **Exploration/Joy**: A goal focused on hobbies, creativity, social
           connection, or pure curiosity (low pressure).

        Philosophy:
        1. **Career goal** should fit the "Deep Work" philosophy (High value, challenging).
        2. **Health goal** should be sustainable and restorative.
        3. **Joy goal** should be fun and expanding the soul.

        For each goal, provide:
        - title: A concise, inspiring title (In Chinese)
        - description: A clear description (In Chinese)
        - resource_description: Resources needed (In Chinese)
        - target_level: Success criteria (In Chinese)
        - tags: A list of tags, e.g. ["Career"], ["Health"], ["Hobby"]
        - id: a unique short string

        Return ONLY a valid JSON array of objects.
        IMPORTANT: All text content MUST be in Simplified Chinese.

        Example:
        [
            {{
                "id": "g1",
                "title": "从零实现 Transformer",
                "description": "手写 Attention 机制，彻底理解 LLM 核心。",
                "tags": ["Career", "AI"],
                ...
            }},
            {{
                "id": "g2",
                "title": "早起光照与冥想",
                "description": "每天早起接受10分钟自然光照并冥想。",
                "tags": ["Health", "Routine"],
                ...
            }},
            {{
                "id": "g3",
                "title": "精酿啤酒品鉴",
                "description": "学习品鉴不同风格的精酿啤酒并记录。",
                "tags": ["Hobby", "Fun"],
                ...
            }}
        ]
        """

    def _parse_response(self, content: str) -> List[Dict]:
        """解析 LLM 返回的 JSON"""
        try:
            # Clean up markdown code blocks if present
            cleaned = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM: {content}")
            return []

    def decompose_to_children(
        self,
        parent_goal: Goal,
        profile: UserProfile,
        n: int = 4,
        context: dict = None,
        existing_titles: List[str] = None,
    ) -> List[Dict]:
        """
        将父目标分解为子目标候选列表，带完成概率预估

        Args:
            parent_goal: 父目标
            profile: 用户画像
            n: 生成候选数量
            context: 用户回答的额外上下文信息
            existing_titles: 已存在的子目标标题列表（用于去重）

        Returns:
            子目标候选列表 [{"title": "...", "description": "...", "probability": 75}]
        """
        logger.info(f"Decomposing goal: {parent_goal.title}")

        # 确定子目标层级
        child_type = {
            "vision": "里程碑（1-3年可达成的阶段性成就）",
            "milestone": "具体目标（1-3个月可完成的目标）",
            "goal": "子目标（更细分的目标）"
        }.get(parent_goal.horizon, "子目标")

        # 构建额外上下文
        context_str = ""
        if context:
            context_str += "\n用户补充信息:\n"
            for k, v in context.items():
                context_str += f"- {k}: {v}\n"

        if existing_titles:
            context_str += "\n已存在的相关目标(请避免重复，提供新的视角):\n"
            for t in existing_titles:
                context_str += f"- {t}\n"

        prompt = f"""
        你是一个专业的目标规划师。请将以下目标分解为 {n} 个{child_type}选项。

        父目标: {parent_goal.title}
        描述: {parent_goal.description}

        用户背景:
        - 职业: {profile.occupation}
        - 关注领域: {profile.focus_area}
        - 每日可用时间: {profile.daily_hours}
        {context_str}

        要求:
        1. 每个选项应该是达成父目标的一个可行路径
        2. 选项之间应该有差异性（不同方法/方向）
        3. 标题简洁有力，描述清晰具体，不要包含"选项X"等前缀
        4. 根据用户背景评估每个选项的完成概率（0-100%）
        5. 全部使用中文（包括标题、描述、原因）
        6. 如果已有目标，请生成与其互补或进阶的选项，严禁生成语义重复的内容

        返回 JSON 数组格式:
        [
            {{"title": "标题", "description": "具体描述", "probability": 75, "reason": "预估原因"}},
            ...
        ]

        只返回 JSON，不要其他内容。
        """

        try:
            response = self.llm.generate(prompt)
            if not response.success:
                logger.error(f"LLM decomposition failed: {response.error}")
                return self._fallback_options(parent_goal, n)

            options = self._parse_response(response.content)
            if not options:
                return self._fallback_options(parent_goal, n)

            # 按概率排序
            options = sorted(options, key=lambda x: x.get('probability', 50), reverse=True)
            return options[:n]

        except Exception as e:
            logger.error(f"Goal decomposition failed: {e}", exc_info=True)
            return self._fallback_options(parent_goal, n)

    def get_feasibility_questions(self, parent_goal: Goal, profile: UserProfile) -> List[Dict]:
        """
        获取评估目标可行性所需的问题

        Returns:
            问题列表 [{"id": "q1", "question": "问题内容", "options": ["选项1", "选项2"]}]
        """
        logger.info(f"Getting feasibility questions for: {parent_goal.title}")

        prompt = f"""
        你是一个目标规划师。在帮助用户将愿景分解为具体目标之前，你需要了解一些关键信息。

        用户愿景: {parent_goal.title}
        描述: {parent_goal.description}

        用户背景:
        - 职业: {profile.occupation}
        - 关注领域: {profile.focus_area}

        请生成 2-3 个关键问题，帮助评估可行性和选择合适的路径。
        每个问题都必须提供 3-4 个常见选项，方便用户快速选择。

        重要约束:
        - 所有问题和选项必须使用中文
        - 问题应具体且针对该愿景

        返回 JSON 数组:
        [
            {{
                "id": "q1",
                "question": "你目前在这个领域的经验水平？",
                "options": ["零基础", "了解一些概念", "有实战经验", "专家水平"]
            }}
        ]

        只返回 JSON。
        """

        try:
            response = self.llm.generate(prompt)
            if not response.success:
                return self._fallback_questions()

            questions = self._parse_response(response.content)
            if not questions:
                return self._fallback_questions()

            return questions[:3]
        except Exception as e:
            logger.error(f"Failed to get questions: {e}")
            return self._fallback_questions()

    def _fallback_questions(self) -> List[Dict]:
        """备选问题"""
        return [
            {
                "id": "q1",
                "question": "你目前在这个领域的经验水平？",
                "options": ["新手", "有一定经验", "专家"],
            },
            {
                "id": "q2",
                "question": "你每周可以投入多少时间？",
                "options": ["<5小时", "5-10小时", "10-20小时", ">20小时"],
            },
        ]

    def _fallback_options(self, parent_goal: Goal, n: int) -> List[Dict]:
        """LLM 失败时的备选选项"""
        return [
            {
                "title": f"{parent_goal.title} - 方式 {i+1}",
                "description": "请自定义描述",
                "probability": 50,
            }
            for i in range(n)
        ]
