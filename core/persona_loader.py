"""
Persona Loader — 读取 config/persona/ 文件和 Blueprint，拼装 Guardian system prompt。
"""
from pathlib import Path
from typing import Optional

PERSONA_DIR = Path(__file__).parent.parent / "config" / "persona"
BLUEPRINT_PATH = Path(__file__).parent.parent / "docs" / "concepts" / "better_human_blueprint.md"


def get_persona_section(filename: str) -> str:
    path = PERSONA_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def get_blueprint_anchor() -> str:
    """
    读取 better_human_blueprint.md，提取核心内容返回精简摘要。
    作为 Guardian 决策的最高优先级锚点。
    """
    if not BLUEPRINT_PATH.exists():
        return ""

    content = BLUEPRINT_PATH.read_text(encoding="utf-8")

    # 提取核心哲学（Section 1）
    philosophy = "To Automate the Mundane, so the Extraordinary can Bloom."

    # 提取三个 Goal 的标题和 Life Metric
    goals = [
        ("Goal 1 Deep Wisdom", "创造了多少新的思想连接"),
        ("Goal 2 Peak Experience", "每日心流时长"),
        ("Goal 3 Radical Connection", "深度对话次数"),
    ]

    # 两个核心痛苦来源（Section 4）
    pains = [
        "被本能劫持（多巴胺回路）",
        "被琐事淹没",
    ]

    # 组装摘要
    lines = [
        "## Blueprint Anchor（用户清醒意志，最高优先级）",
        f"- 核心哲学：{philosophy}",
    ]
    for goal_title, metric in goals:
        lines.append(f"- {goal_title}：Life Metric = {metric}")
    for i, pain in enumerate(pains, 1):
        lines.append(f"- 需要守护的两个痛苦：{chr(0x2460 + i - 1)} {pain}")

    return "\n".join(lines)


def get_persona() -> dict:
    return {
        "soul": get_persona_section("SOUL.md"),
        "identity": get_persona_section("IDENTITY.md"),
        "user": get_persona_section("USER.md"),
        "agents": get_persona_section("AGENTS.md"),
    }


def get_guardian_system_prompt(sub_role: Optional[str] = None) -> str:
    persona = get_persona()

    # Blueprint 作为最高优先级，放在最前面
    blueprint_anchor = get_blueprint_anchor()

    parts = []
    if blueprint_anchor:
        parts.append(blueprint_anchor)
    parts.append(persona["soul"])
    parts.append(persona["identity"])

    user_section = persona["user"].strip()
    if user_section:
        parts.append(user_section)

    # AGENTS 作为工作规范压轴
    agents_section = persona["agents"].strip()
    if agents_section:
        parts.append(agents_section)

    prompt = "\n\n---\n\n".join(p for p in parts if p.strip())
    if sub_role:
        prompt += f"\n\n当前激活子角色触发信号：{sub_role}"
    return prompt
