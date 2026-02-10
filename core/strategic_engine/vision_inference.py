from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json

from core.llm_adapter import get_llm
from core.strategic_engine.bhb_parser import parse_bhb
from core.strategic_engine.info_sensing import search_market_trends
from core.utils import load_prompt, parse_llm_json


@dataclass
class InferredVision:
    """推断出的 Vision"""
    title: str
    description: str
    target_outcome: str              # 可量化的目标结果
    confidence: float                # 置信度 0-1
    reasoning_chain: List[str]       # 推理链
    information_edge: List[str]      # 信息差洞察
    source_signals: Dict[str, Any]   # 推断依据
    bhb_alignment: str               # 与 BHB 的对齐描述


def infer_vision(
    state: Dict[str, Any],
    enable_search: bool = True,
    search_limit: int = 3
) -> Optional[InferredVision]:
    """
    Vision 推断主函数。

    推断逻辑:
    1. 收集用户状态 (identity, skills, constraints)
    2. 解析 BHB 获取哲学方向
    3. [可选] 调用搜索获取市场信息
    4. 调用 LLM 综合推断 Vision

    Args:
        state: 当前系统状态
        enable_search: 是否启用搜索 (False 用于测试或离线模式)
        search_limit: 搜索查询次数上限

    Returns:
        InferredVision 或 None (如果推断失败)
    """
    # 1. 收集信息
    identity = state.get("identity", {})
    skills = state.get("capability", {}).get("skills", [])
    constraints = state.get("constraints", {})

    # 2. 解析 BHB
    bhb_config = parse_bhb()

    # 3. 搜索市场信息 (如果启用)
    search_results = []
    if enable_search and skills:
        # 基于技能生成搜索查询
        primary_skill = skills[0] if isinstance(skills, list) else str(skills)
        search_results = search_market_trends(
            skill=primary_skill,
            location=identity.get("city", "China"),
            limit=search_limit
        )

    # 4. 构建 Prompt
    llm = get_llm("strategic_brain")
    system_prompt = load_prompt("vision_synthesis")

    if not system_prompt:
        system_prompt = _default_vision_prompt()

    context = {
        "identity": identity,
        "skills": skills,
        "constraints": constraints,
        "bhb_philosophy": bhb_config.philosophy,
        "bhb_goals": bhb_config.strategic_goals,
        "bhb_metrics": [m.description for m in bhb_config.life_metrics],
        "market_insights": search_results
    }

    prompt = f"""请基于以下信息，推断一个高价值的人生愿景 (Vision)。

用户信息:
{json.dumps(context, ensure_ascii=False, indent=2)}

要求:
1. Vision 必须具体、可量化、有时间边界
2. 必须利用"信息差"——提供用户可能不知道但应该知道的洞察
3. 必须与用户的 BHB 哲学对齐
4. 输出 JSON 格式

输出格式:
```json
{{
  "title": "Vision 标题",
  "description": "详细描述",
  "target_outcome": "可量化目标 (如: 年收入 50 万)",
  "confidence": 0.75,
  "reasoning_chain": [
    "推理步骤 1...",
    "推理步骤 2..."
  ],
  "information_edge": [
    "用户可能不知道的信息 1...",
    "用户可能不知道的信息 2..."
  ],
  "bhb_alignment": "与 BHB 的对齐说明"
}}
```"""

    # 5. 调用 LLM
    try:
        response = llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1500
        )

        if response.success and response.content:
            result = parse_llm_json(response.content)
            if result:
                return InferredVision(
                    title=result.get("title", "未命名愿景"),
                    description=result.get("description", ""),
                    target_outcome=result.get("target_outcome", ""),
                    confidence=result.get("confidence", 0.5),
                    reasoning_chain=result.get("reasoning_chain", []),
                    information_edge=result.get("information_edge", []),
                    source_signals={
                        "identity": identity,
                        "skills": skills,
                        "search_results": search_results
                    },
                    bhb_alignment=result.get("bhb_alignment", "")
                )
    except Exception as e:
        print(f"[VisionInference] Failed: {e}")

    return None


def _default_vision_prompt() -> str:
    """默认 System Prompt"""
    return """你是一个战略规划师。你的任务是为用户推断一个高价值的人生愿景 (Vision)。

核心原则:
1. 利用信息差 - 提供用户通过常规方式难以获得的洞察
2. 基于现实 - Vision 必须可达成，考虑用户的约束条件
3. 对齐价值 - Vision 必须与用户的深层价值观 (BHB) 一致
4. 具体量化 - 避免空洞的"成为更好的人"，而是"18个月内年收入达到X"

禁止:
- 生成泛泛而谈的目标 (如"提升编程能力")
- 忽略用户的约束条件
- 输出无法验证的目标"""
