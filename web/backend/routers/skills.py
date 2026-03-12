"""
Skills API Router for AI Life OS.

提供 Skills 查询接口。
"""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SkillSummary(BaseModel):
    """Skill 摘要模型。"""
    name: str
    description: str
    enabled: bool


class SkillDetail(BaseModel):
    """Skill 详情模型。"""
    name: str
    description: str
    enabled: bool
    requires: dict
    content: str
    path: str


@router.get("", response_model=List[SkillSummary])
async def list_skills():
    """
    列出所有可用 Skills。

    Returns:
        Skills 列表,包含 name, description, enabled
    """
    try:
        from core.skill_loader import load_skills

        skills = load_skills()

        return [
            SkillSummary(
                name=skill.name,
                description=skill.description,
                enabled=skill.enabled
            )
            for skill in skills
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载 Skills 失败: {str(e)}")


@router.get("/{name}", response_model=SkillDetail)
async def get_skill_detail(name: str):
    """
    获取单个 Skill 内容。

    Args:
        name: Skill 名称

    Returns:
        Skill 完整信息,包含 content
    """
    try:
        from core.skill_loader import get_skill

        skill = get_skill(name)

        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")

        return SkillDetail(
            name=skill.name,
            description=skill.description,
            enabled=skill.enabled,
            requires=skill.requires,
            content=skill.content,
            path=str(skill.path) if skill.path else ""
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Skill 失败: {str(e)}")
