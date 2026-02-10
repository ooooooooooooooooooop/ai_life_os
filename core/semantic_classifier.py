"""
Semantic Classifier for AI Life OS.

使用 LLM 进行语义分类，替代硬编码的关键词匹配。
"""
from typing import Any, Dict, Optional

from core.llm_adapter import get_llm
from core.utils import load_prompt, parse_llm_json


def classify_action(description: str) -> Optional[Dict[str, Any]]:
    """
    使用 LLM 对 Action 进行语义分类，推断验证方式。

    Args:
        description: Action 描述

    Returns:
        验证配置字典，如 {"type": "file_system", "target": "notes/..."}
        分类失败返回 None

    注意：
        使用 cost_efficient 模型以降低延迟和成本。
    """
    llm = get_llm("cost_efficient")  # 使用低成本模型

    prompt = load_prompt("classification/verification", variables={
        "description": description
    })

    if not prompt:
        # Prompt 缺失时回退到 None（保持原有行为）
        return None

    try:
        response = llm.generate(prompt, temperature=0.3, max_tokens=200)
        if response.success:
            result = parse_llm_json(response.content)
            if result and result.get("type") != "none":
                return {
                    "type": result.get("type", "manual_confirm"),
                    "target": result.get("target", "")
                }
    except Exception as e:
        print(f"[SemanticClassifier] Classification failed: {e}")

    return None
