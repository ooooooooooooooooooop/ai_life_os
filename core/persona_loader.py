"""
Persona Loader — 读取 config/persona/ 三个文件，拼装 Guardian system prompt。
"""
from pathlib import Path
from typing import Optional

PERSONA_DIR = Path(__file__).parent.parent / "config" / "persona"

def get_persona_section(filename: str) -> str:
    path = PERSONA_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")

def get_persona() -> dict:
    return {
        "soul": get_persona_section("SOUL.md"),
        "identity": get_persona_section("IDENTITY.md"),
        "user": get_persona_section("USER.md"),
    }

def get_guardian_system_prompt(sub_role: Optional[str] = None) -> str:
    persona = get_persona()
    parts = [persona["soul"], persona["identity"]]
    user_section = persona["user"].strip()
    if user_section:
        parts.append(user_section)
    prompt = "\n\n---\n\n".join(p for p in parts if p.strip())
    if sub_role:
        prompt += f"\n\n当前激活子角色触发信号：{sub_role}"
    return prompt
