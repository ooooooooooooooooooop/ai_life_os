import os
from pathlib import Path
from typing import Any, Dict, Optional

# Prompt 模板目录
PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def load_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """
    加载 Prompt 模板文件，支持子目录和变量注入。
    
    Args:
        name: Prompt 名称，支持子目录 (如 "inference/goal_system")
        variables: 变量字典，用于替换 {var} 占位符
        
    Returns:
        渲染后的 Prompt 字符串
        
    Example:
        load_prompt("inference/goal_user", {"identity": "...", "skills": "..."})
    """
    # 支持子目录 (使用 os.sep 确保跨平台兼容)
    prompt_path = PROMPTS_DIR / f"{name.replace('/', os.sep)}.md"
    
    if not prompt_path.exists():
        print(f"[PromptManager] Warning: Prompt '{name}' not found at {prompt_path}")
        return ""
    
    template = prompt_path.read_text(encoding="utf-8")
    
    # 变量注入
    if variables:
        for key, value in variables.items():
            # 支持 {var} 格式的占位符
            template = template.replace(f"{{{key}}}", str(value))
    
    return template

def read_file_safe(path_str: str, encoding: str = "utf-8") -> str:
    """Safely read file context, returning empty string if failed."""
    try:
        p = Path(path_str)
        # Handle relative paths from project root
        if not p.is_absolute():
            # Assuming core/utils.py is 2 levels deep from root
            root = Path(__file__).parent.parent
            p = root / path_str
            
        if p.exists() and p.is_file():
            return p.read_text(encoding=encoding)
    except Exception as e:
        print(f"Failed to read file {path_str}: {e}")
    return ""

import json
from typing import Any, Dict, Optional


def parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    """
    解析 LLM 返回的 JSON 内容。
    
    LLM 经常将 JSON 包裹在 Markdown 代码块中，此函数自动处理这些情况。
    
    Args:
        content: LLM 返回的原始内容
        
    Returns:
        解析后的字典，解析失败返回 None
        
    示例:
        >>> parse_llm_json('```json\\n{"key": "value"}\\n```')
        {'key': 'value'}
    """
    if not content:
        return None
    
    # 尝试提取 Markdown 代码块中的 JSON
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return None
