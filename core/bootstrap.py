"""
Bootstrap module for AI Life OS.

Handles cold start: when state is empty, inject initial setup tasks.
"""
from typing import Any, Dict, List


def is_cold_start(state: Dict[str, Any]) -> bool:
    """
    Determine if this is a cold start (empty state).
    
    Args:
        state: Current state dictionary.
    
    Returns:
        True if state indicates cold start, False otherwise.
    """
    # Cold start conditions:
    # 1. No identity info
    # 2. No time state
    # 3. No active tasks
    identity = state.get("identity", {})
    time_state = state.get("time_state", {})
    
    has_identity = bool(identity.get("city") or identity.get("occupation"))
    has_time = bool(time_state.get("current_date"))
    
    return not (has_identity and has_time)


def get_bootstrap_tasks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate initial setup tasks for cold start using LLM.
    
    Args:
        state: Current system state.
        
    Returns:
        List of bootstrap task dictionaries.
    """
    # 1. Try to use LLM for dynamic questions
    try:
        from core.llm_adapter import get_llm
        from core.utils import load_prompt, parse_llm_json
        import json
        
        llm = get_llm("strategic_brain")
        prompt_template = load_prompt("bootstrap_generator")
        
        if prompt_template and llm.get_model_name() != "rule_based":
            system_prompt = prompt_template.replace("{{current_state}}", json.dumps(state, ensure_ascii=False))
            
            response = llm.generate(
                prompt="请生成初始化引导任务。",
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1000
            )
            
            if response.success and response.content:
                tasks = parse_llm_json(response.content)
                if tasks and isinstance(tasks, list):
                    return tasks
                    
    except Exception as e:
        print(f"[Bootstrap] Dynamic generation failed: {e}.")
        # 3. Principle: Do not mask the problem with hardcoded fallbacks.
        # Report the system failure as a maintenance task.
        return [
            {
                "id": "sys_repair_llm",
                "description": f"系统故障: 无法生成初始化向导 (错误: {str(e)})。请检查本地模型服务。",
                "priority": "maintenance",
                "question_type": "yes_no", # Confirms fix
                "target_field": "system.health.llm_status"
            }
        ]
        
    # If we get here, something unexpected happened but no exception raised
    return []
