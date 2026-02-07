"""
Goal Inference Engine for AI Life OS.

Uses 'strategic_brain' (GPT-5.2) to infer potential high-value goals
based on user identity, skills, and constraints.
"""
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.llm_adapter import get_llm


@dataclass
class InferredGoal:
    title: str
    description: str
    reasoning: str
    confidence: float


def infer_goals_from_state(state: Dict[str, Any]) -> List[InferredGoal]:
    """
    Infer potential goals from the current world state.
    
    Args:
        state: Current system state (identity, skills, etc.)
        
    Returns:
        List of InferredGoal objects.
    """
    llm = get_llm("strategic_brain")
    
    # 1. Prepare Context
    identity = state.get("identity", {})
    skills = state.get("capability", {}).get("skills", [])
    constraints = state.get("constraints", {})
    
    # Skip only if absolutely no info is available (true cold start)
    # The Strategic Engine can now infer goals even with minimal info (using Search/BHB)
    # if not identity.get("occupation") and not identity.get("city") and not skills:
    #    return []

    # 2. Build Prompt (从外部文件加载，支持热更新)
    from core.utils import load_prompt
    
    system_prompt = load_prompt("inference/goal_system")
    if not system_prompt:
        print("[GoalInference] Warning: System prompt not found, using fallback")
        system_prompt = "你是一个务实的项目经理。定义 1 个核心项目。"
    
    prompt = load_prompt("inference/goal_user", variables={
        "identity": json.dumps(identity, ensure_ascii=False, indent=2),
        "skills": json.dumps(skills, ensure_ascii=False),
        "constraints": json.dumps(constraints, ensure_ascii=False)
    })
    
    if not prompt:
        # Fallback: 使用简单格式
        prompt = f"用户画像: {identity}\n技能: {skills}\n约束: {constraints}\n请定义 1 个核心项目，输出 JSON。"

    # 3. Call LLM
    try:
        response = llm.generate(
            prompt, 
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1000
        )
        
        if response.success:
            return _parse_response(response.content)
            
    except Exception as e:
        print(f"[GoalInference] Failed: {e}")
        
    return []


def _parse_response(content: str) -> List[InferredGoal]:
    """Parse LLM JSON response."""
    goals = []
    try:
        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        data = json.loads(content.strip())
        
        for item in data:
            goals.append(InferredGoal(
                title=item.get("title", "未知目标"),
                description=item.get("description", ""),
                reasoning=item.get("reasoning", ""),
                confidence=item.get("confidence", 0.5)
            ))
            
    except (json.JSONDecodeError, KeyError):
        pass
        
    return goals
