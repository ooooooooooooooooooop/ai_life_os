"""
Task Decomposer for AI Life OS.
Decomposes high-level goals into specific, actionable tasks using LLM.
"""
import json
import logging
from datetime import date, timedelta
from typing import List, Dict
from core.models import Goal, Task, TaskStatus
from core.llm_adapter import get_llm

logger = logging.getLogger("task_decomposer")

class TaskDecomposer:
    """任务分解器"""

    def __init__(self):
        # Use simple model for decomposition as it's more structured
        self.llm = get_llm()

    def decompose_goal(self, goal: Goal, start_date: date) -> List[Task]:
        """
        将目标分解为一系列任务。
        """
        logger.info(f"Decomposing goal: {goal.title}")

        prompt = self._build_prompt(goal)

        try:
            response = self.llm.generate(prompt)
            if not response.success:
                logger.error(f"LLM decomposition failed: {response.error}")
                return []

            raw_tasks = self._parse_response(response.content)

            tasks = []
            for i, item in enumerate(raw_tasks):
                # Calculate simple schedule: 1 task per day for now
                # Phase 2 TODO: Smarter scheduling logic
                scheduled_date = start_date + timedelta(days=i)

                task = Task(
                    id=f"{goal.id}_t{i+1}",
                    goal_id=goal.id,
                    description=item.get("description", ""),
                    scheduled_date=scheduled_date,
                    estimated_minutes=item.get("minutes", 30),
                    status=TaskStatus.PENDING,
                    scheduled_time=item.get("time_of_day", "Anytime") # e.g. "Morning", "14:00"
                )
                tasks.append(task)

            return tasks

        except Exception as e:
            logger.error(f"Task decomposition failed: {e}", exc_info=True)
            return []

    def _build_prompt(self, goal: Goal) -> str:
        return f"""
        You are an expert Project Manager.
        Decompose the following goal into a concrete, sequential learning path or action plan.

        Goal: {goal.title}
        Description: {goal.description}
        Resources: {goal.resource_description}
        Target Level: {goal.target_level}

        Requirements:
        1. Break it down into small, bite-sized tasks (30-60 mins each).
        2. Tasks must be ACTIONABLE.
           Bad: "Learn variable". Good: "阅读第1章并编写 Hello World 脚本".
        3. Initial plan should be about 5-7 tasks (for the first week).
        4. ALL Output must be in Simplified Chinese (简体中文).

        Return ONLY a JSON array of objects.
        Example:
        [
            {{
                "description": "阅读 Rust 所有权相关文档",
                "minutes": 45,
                "time_of_day": "Morning"
            }},
            {{
                "description": "在 Rust 中实现一个链表 (fail, then fix)",
                "minutes": 60,
                "time_of_day": "Evening"
            }}
        ]
        """

    def _parse_response(self, content: str) -> List[Dict]:
        try:
            cleaned = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warn(f"Failed to parse JSON task list: {content}")
            return []
