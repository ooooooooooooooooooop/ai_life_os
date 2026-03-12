"""
Skill Loader for AI Life OS.

扫描 skills/ 目录,读取每个子目录下的 SKILL.md。
解析 YAML frontmatter,支持按条件加载。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Skills 目录路径
SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class Skill:
    """Skill 数据模型。"""
    name: str
    description: str
    enabled: bool = True
    requires: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "requires": self.requires,
            "content": self.content,
            "path": str(self.path) if self.path else None
        }


class SkillLoader:
    """Skill 加载器。"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def load_skills(self) -> List[Skill]:
        """
        返回所有可用 Skill。

        Returns:
            Skill 列表
        """
        if not self.skills_dir.exists():
            return []

        skills = []
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            skill = self._load_skill_file(skill_file)
            if skill:
                skills.append(skill)

        return skills

    def get_skill(self, name: str) -> Optional[Skill]:
        """
        获取单个 Skill。

        Args:
            name: Skill 名称

        Returns:
            Skill 对象或 None
        """
        skills = self.load_skills()
        for skill in skills:
            if skill.name == name:
                return skill
        return None

    def build_system_prompt(self, skill_names: List[str]) -> str:
        """
        拼装多个 Skill 的内容到 system prompt。

        Args:
            skill_names: Skill 名称列表

        Returns:
            拼装后的 system prompt
        """
        prompts = []
        for name in skill_names:
            skill = self.get_skill(name)
            if skill and skill.enabled:
                prompts.append(f"## {skill.name}\n\n{skill.content}")

        if not prompts:
            return ""

        return "\n\n---\n\n".join(prompts)

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _load_skill_file(self, skill_file: Path) -> Optional[Skill]:
        """
        加载单个 SKILL.md 文件。

        Args:
            skill_file: SKILL.md 文件路径

        Returns:
            Skill 对象或 None
        """
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析 YAML frontmatter
            frontmatter, body = self._parse_frontmatter(content)

            if not frontmatter:
                print(f"[SkillLoader] 警告: {skill_file} 缺少 frontmatter")
                return None

            return Skill(
                name=frontmatter.get("name", skill_file.parent.name),
                description=frontmatter.get("description", ""),
                enabled=frontmatter.get("enabled", True),
                requires=frontmatter.get("requires", {}),
                content=body.strip(),
                path=skill_file
            )

        except Exception as e:
            print(f"[SkillLoader] 加载 {skill_file} 失败: {e}")
            return None

    def _parse_frontmatter(self, content: str) -> tuple:
        """
        解析 YAML frontmatter。

        Args:
            content: 文件内容

        Returns:
            (frontmatter_dict, body_content)
        """
        # 匹配 --- 包围的 frontmatter
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}, content

        frontmatter_str = match.group(1)
        body = match.group(2)

        # 解析 YAML
        try:
            import yaml
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except Exception as e:
            print(f"[SkillLoader] YAML 解析失败: {e}")
            return {}, content

        return frontmatter, body


# 单例实例
_loader_instance: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """获取 SkillLoader 单例实例。"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = SkillLoader()
    return _loader_instance


def load_skills() -> List[Skill]:
    """便捷函数:加载所有 Skills。"""
    return get_skill_loader().load_skills()


def get_skill(name: str) -> Optional[Skill]:
    """便捷函数:获取单个 Skill。"""
    return get_skill_loader().get_skill(name)


def build_system_prompt(skill_names: List[str]) -> str:
    """便捷函数:构建 system prompt。"""
    return get_skill_loader().build_system_prompt(skill_names)
