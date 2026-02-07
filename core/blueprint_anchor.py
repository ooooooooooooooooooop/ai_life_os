"""
Blueprint Anchor Layer - 冻结清醒意志的结构化快照

核心原则：
- 只读，运行时不可修改
- 只在用户清醒确认时更新
- 可审计，决策可引用具体条目

Spec-Driven 约束：
- temperature=0 (ANCHOR_EXTRACTION 模式)
- 禁止补全/想象/推演
- 输出必须可 audit
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
import json
import hashlib
import re

from core.llm_adapter import get_llm

# 存储路径
ANCHOR_DIR = Path(__file__).parent.parent / "data" / "anchors"
CURRENT_ANCHOR_PATH = ANCHOR_DIR / "current.json"
HISTORY_DIR = ANCHOR_DIR / "history"


@dataclass(frozen=True)
class BlueprintAnchor:
    """
    不可变的 Blueprint 锚点
    
    frozen=True 确保运行时不可修改
    所有 List 字段使用 tuple 保证不可变性
    """
    version: str
    created_at: str  # ISO format
    confirmed_by_user: bool
    
    # 核心字段 (tuple for immutability)
    non_negotiables: tuple        # 不可谈判底线
    long_horizon_commitments: tuple  # 长期承诺
    anti_values: tuple            # 反价值
    instinct_adversaries: tuple   # 本能劫持模式
    
    # 来源追溯
    source_file: str              # Blueprint 文件路径
    source_hash: str              # 文件内容 hash (可审计)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "confirmed_by_user": self.confirmed_by_user,
            "non_negotiables": list(self.non_negotiables),
            "long_horizon_commitments": list(self.long_horizon_commitments),
            "anti_values": list(self.anti_values),
            "instinct_adversaries": list(self.instinct_adversaries),
            "source_file": self.source_file,
            "source_hash": self.source_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlueprintAnchor":
        """从字典创建"""
        return cls(
            version=data["version"],
            created_at=data["created_at"],
            confirmed_by_user=data["confirmed_by_user"],
            non_negotiables=tuple(data["non_negotiables"]),
            long_horizon_commitments=tuple(data["long_horizon_commitments"]),
            anti_values=tuple(data["anti_values"]),
            instinct_adversaries=tuple(data["instinct_adversaries"]),
            source_file=data["source_file"],
            source_hash=data["source_hash"]
        )
    
    def is_matching_pattern(self, behavior: str, pattern: str) -> bool:
        """检查行为是否匹配本能劫持模式"""
        return pattern.lower() in behavior.lower()
    
    def check_instinct_hijack(self, behavior: str) -> Optional[str]:
        """
        检查行为是否触发本能劫持模式
        
        Returns:
            匹配的模式字符串，如果无匹配返回 None
        """
        for pattern in self.instinct_adversaries:
            if self.is_matching_pattern(behavior, pattern):
                return pattern
        return None


class AnchorExtractor:
    """
    从 Blueprint 提取 Anchor (ANCHOR_EXTRACTION 模式)
    
    ANCHOR_EXTRACTION 模式要求：
    - temperature ≈ 0
    - 禁止补全/想象/推演
    - 输出必须可 audit（追溯到原文）
    """
    
    EXTRACTION_PROMPT = """请分析以下 Blueprint 文档，提取结构化信息。

**严格规则**：
1. 只提取文档中**明确表达**的内容
2. 禁止补全、推演或添加文档中未提及的内容
3. 每个提取项必须能在原文中找到依据
4. 如果某个类别在原文中没有明确内容，返回空数组

请输出 JSON 格式：
```json
{{
  "non_negotiables": ["..."],          // 不可谈判的底线、必须遵守的原则
  "long_horizon_commitments": ["..."], // 长期承诺、战略目标
  "anti_values": ["..."],              // 明确反对的状态、不想成为的样子
  "instinct_adversaries": ["..."]      // 需要对抗的本能、冲动、劫持模式
}}
```

Blueprint 文档内容：
---
{blueprint_content}
---

请只输出 JSON，不要其他解释。"""
    
    def extract(self, blueprint_path: str) -> Dict[str, List[str]]:
        """
        从 Blueprint 提取锚点字段
        
        Args:
            blueprint_path: Blueprint 文件路径
            
        Returns:
            提取的锚点字段字典
        """
        content = Path(blueprint_path).read_text(encoding="utf-8")
        
        # 使用 ANCHOR_EXTRACTION 模式：temperature=0
        llm = get_llm()
        
        response = llm.generate(
            prompt=self.EXTRACTION_PROMPT.format(blueprint_content=content),
            temperature=0.0,  # ANCHOR_EXTRACTION 模式：禁止随机性
            max_tokens=2000
        )
        
        # 解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', response.content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON 解析失败: {e}")
        
        raise ValueError("无法从 LLM 响应中提取 JSON")


@dataclass
class AnchorDiff:
    """Anchor 差异结果"""
    status: str  # "new" | "changed" | "unchanged"
    version_change: Optional[str] = None
    added_non_negotiables: Set[str] = None
    removed_non_negotiables: Set[str] = None
    added_commitments: Set[str] = None
    removed_commitments: Set[str] = None
    added_anti_values: Set[str] = None
    removed_anti_values: Set[str] = None
    added_adversaries: Set[str] = None
    removed_adversaries: Set[str] = None
    
    def has_changes(self) -> bool:
        """检查是否有任何变更"""
        if self.status == "new":
            return True
        if self.status == "unchanged":
            return False
        
        return any([
            self.added_non_negotiables,
            self.removed_non_negotiables,
            self.added_commitments,
            self.removed_commitments,
            self.added_anti_values,
            self.removed_anti_values,
            self.added_adversaries,
            self.removed_adversaries
        ])


class AnchorManager:
    """
    管理 Anchor 生命周期
    
    职责：
    - 获取当前 Anchor（只读）
    - 生成新 Anchor 草稿
    - 计算差异
    - 激活新 Anchor（需用户确认）
    """
    
    def __init__(self):
        self.extractor = AnchorExtractor()
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保存储目录存在"""
        ANCHOR_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_current(self) -> Optional[BlueprintAnchor]:
        """
        获取当前 Anchor（只读）
        
        Returns:
            当前激活的 Anchor，如果不存在返回 None
        """
        if not CURRENT_ANCHOR_PATH.exists():
            return None
        
        try:
            data = json.loads(CURRENT_ANCHOR_PATH.read_text(encoding="utf-8"))
            return BlueprintAnchor.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[警告] Anchor 文件损坏: {e}")
            return None
    
    def generate_draft(self, blueprint_path: str) -> BlueprintAnchor:
        """
        生成新 Anchor 草稿（未确认）
        
        Args:
            blueprint_path: Blueprint 文件路径
            
        Returns:
            未确认的 Anchor 草稿
        """
        path = Path(blueprint_path)
        if not path.exists():
            raise FileNotFoundError(f"Blueprint 文件不存在: {blueprint_path}")
        
        content = path.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # 提取字段
        extracted = self.extractor.extract(blueprint_path)
        
        # 生成版本号
        current = self.get_current()
        if current:
            try:
                version_num = int(current.version.replace("v", "")) + 1
            except ValueError:
                version_num = 1
        else:
            version_num = 1
        
        return BlueprintAnchor(
            version=f"v{version_num}",
            created_at=datetime.now().isoformat(),
            confirmed_by_user=False,  # 未确认
            non_negotiables=tuple(extracted.get("non_negotiables", [])),
            long_horizon_commitments=tuple(extracted.get("long_horizon_commitments", [])),
            anti_values=tuple(extracted.get("anti_values", [])),
            instinct_adversaries=tuple(extracted.get("instinct_adversaries", [])),
            source_file=str(path.absolute()),
            source_hash=source_hash
        )
    
    def diff(self, old: Optional[BlueprintAnchor], new: BlueprintAnchor) -> AnchorDiff:
        """
        计算两个 Anchor 的差异
        
        Args:
            old: 旧 Anchor（可为 None）
            new: 新 Anchor
            
        Returns:
            差异结果
        """
        if old is None:
            return AnchorDiff(status="new")
        
        # 检查是否完全相同
        if (old.non_negotiables == new.non_negotiables and
            old.long_horizon_commitments == new.long_horizon_commitments and
            old.anti_values == new.anti_values and
            old.instinct_adversaries == new.instinct_adversaries):
            return AnchorDiff(status="unchanged")
        
        return AnchorDiff(
            status="changed",
            version_change=f"{old.version} -> {new.version}",
            added_non_negotiables=set(new.non_negotiables) - set(old.non_negotiables),
            removed_non_negotiables=set(old.non_negotiables) - set(new.non_negotiables),
            added_commitments=set(new.long_horizon_commitments) - set(old.long_horizon_commitments),
            removed_commitments=set(old.long_horizon_commitments) - set(new.long_horizon_commitments),
            added_anti_values=set(new.anti_values) - set(old.anti_values),
            removed_anti_values=set(old.anti_values) - set(new.anti_values),
            added_adversaries=set(new.instinct_adversaries) - set(old.instinct_adversaries),
            removed_adversaries=set(old.instinct_adversaries) - set(new.instinct_adversaries)
        )
    
    def activate(self, anchor: BlueprintAnchor) -> BlueprintAnchor:
        """
        激活 Anchor（用户确认后调用）
        
        这是一个仪式性操作，只有用户显式确认后才能调用。
        
        Args:
            anchor: 待激活的 Anchor 草稿
            
        Returns:
            已确认的 Anchor
        """
        if anchor.confirmed_by_user:
            raise ValueError("Anchor 已确认，无需重复激活")
        
        # 创建已确认版本 (frozen dataclass 需要重新创建)
        confirmed = BlueprintAnchor(
            version=anchor.version,
            created_at=anchor.created_at,
            confirmed_by_user=True,
            non_negotiables=anchor.non_negotiables,
            long_horizon_commitments=anchor.long_horizon_commitments,
            anti_values=anchor.anti_values,
            instinct_adversaries=anchor.instinct_adversaries,
            source_file=anchor.source_file,
            source_hash=anchor.source_hash
        )
        
        # 归档旧版本
        current = self.get_current()
        if current:
            history_filename = f"{current.version}_{current.created_at[:10].replace(':', '-')}.json"
            history_path = HISTORY_DIR / history_filename
            history_path.write_text(
                json.dumps(current.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        
        # 写入新版本
        CURRENT_ANCHOR_PATH.write_text(
            json.dumps(confirmed.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        return confirmed
    
    def list_history(self) -> List[str]:
        """列出所有历史版本"""
        if not HISTORY_DIR.exists():
            return []
        
        return sorted([f.stem for f in HISTORY_DIR.glob("*.json")])
    
    def get_history_version(self, version: str) -> Optional[BlueprintAnchor]:
        """获取历史版本"""
        history_path = HISTORY_DIR / f"{version}.json"
        if not history_path.exists():
            return None
        
        data = json.loads(history_path.read_text(encoding="utf-8"))
        return BlueprintAnchor.from_dict(data)
