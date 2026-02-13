"""
Blueprint Anchor layer.

Anchor is an immutable, auditable snapshot of user-confirmed higher-order values.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import hashlib
import json
import re

from core.llm_adapter import get_llm
from core.paths import DATA_DIR

ANCHOR_DIR = DATA_DIR / "anchors"
CURRENT_ANCHOR_PATH = ANCHOR_DIR / "current.json"
HISTORY_DIR = ANCHOR_DIR / "history"


@dataclass(frozen=True)
class BlueprintAnchor:
    """
    Immutable anchor model.
    """

    version: str
    created_at: str
    confirmed_by_user: bool

    non_negotiables: tuple
    long_horizon_commitments: tuple
    anti_values: tuple
    instinct_adversaries: tuple

    source_file: str
    source_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "confirmed_by_user": self.confirmed_by_user,
            "non_negotiables": list(self.non_negotiables),
            "long_horizon_commitments": list(self.long_horizon_commitments),
            "anti_values": list(self.anti_values),
            "instinct_adversaries": list(self.instinct_adversaries),
            "source_file": self.source_file,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlueprintAnchor":
        return cls(
            version=data["version"],
            created_at=data["created_at"],
            confirmed_by_user=data["confirmed_by_user"],
            non_negotiables=tuple(data["non_negotiables"]),
            long_horizon_commitments=tuple(data["long_horizon_commitments"]),
            anti_values=tuple(data["anti_values"]),
            instinct_adversaries=tuple(data["instinct_adversaries"]),
            source_file=data["source_file"],
            source_hash=data["source_hash"],
        )

    def is_matching_pattern(self, behavior: str, pattern: str) -> bool:
        return pattern.lower() in behavior.lower()

    def check_instinct_hijack(self, behavior: str) -> Optional[str]:
        for pattern in self.instinct_adversaries:
            if self.is_matching_pattern(behavior, pattern):
                return pattern
        return None


class AnchorExtractor:
    """
    Extract structured anchor fields from a blueprint document.
    """

    EXTRACTION_PROMPT = """Analyze the blueprint text and extract only explicitly stated items.

Rules:
1. Do not infer or add content that is not explicitly present.
2. Output must be valid JSON only.
3. If a category is missing, return an empty array for that category.

Output schema:
{
  "non_negotiables": ["..."],
  "long_horizon_commitments": ["..."],
  "anti_values": ["..."],
  "instinct_adversaries": ["..."]
}

Blueprint text:
---
{blueprint_content}
---
"""

    def extract(self, blueprint_path: str) -> Dict[str, List[str]]:
        content = Path(blueprint_path).read_text(encoding="utf-8")
        llm = get_llm()
        response = llm.generate(
            prompt=self.EXTRACTION_PROMPT.format(blueprint_content=content),
            temperature=0.0,
            max_tokens=2000,
        )

        json_match = re.search(r"\{[\s\S]*\}", response.content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                raise ValueError(f"Anchor JSON parse failed: {e}") from e
        raise ValueError("No JSON object found in LLM response")


@dataclass
class AnchorDiff:
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
        if self.status == "new":
            return True
        if self.status == "unchanged":
            return False
        return any(
            [
                self.added_non_negotiables,
                self.removed_non_negotiables,
                self.added_commitments,
                self.removed_commitments,
                self.added_anti_values,
                self.removed_anti_values,
                self.added_adversaries,
                self.removed_adversaries,
            ]
        )


class AnchorManager:
    """
    Manage anchor lifecycle: read current, generate draft, diff, activate, and history.
    """

    def __init__(self):
        self.extractor = AnchorExtractor()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        ANCHOR_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    def get_current(self) -> Optional[BlueprintAnchor]:
        if not CURRENT_ANCHOR_PATH.exists():
            return None
        try:
            data = json.loads(CURRENT_ANCHOR_PATH.read_text(encoding="utf-8"))
            return BlueprintAnchor.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[warning] anchor file corrupted: {e}")
            return None

    def generate_draft(self, blueprint_path: str) -> BlueprintAnchor:
        path = Path(blueprint_path)
        if not path.exists():
            raise FileNotFoundError(f"Blueprint file not found: {blueprint_path}")

        content = path.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        extracted = self.extractor.extract(blueprint_path)

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
            confirmed_by_user=False,
            non_negotiables=tuple(extracted.get("non_negotiables", [])),
            long_horizon_commitments=tuple(extracted.get("long_horizon_commitments", [])),
            anti_values=tuple(extracted.get("anti_values", [])),
            instinct_adversaries=tuple(extracted.get("instinct_adversaries", [])),
            source_file=str(path.absolute()),
            source_hash=source_hash,
        )

    def diff(self, old: Optional[BlueprintAnchor], new: BlueprintAnchor) -> AnchorDiff:
        if old is None:
            return AnchorDiff(status="new")

        if (
            old.non_negotiables == new.non_negotiables
            and old.long_horizon_commitments == new.long_horizon_commitments
            and old.anti_values == new.anti_values
            and old.instinct_adversaries == new.instinct_adversaries
        ):
            return AnchorDiff(status="unchanged")

        return AnchorDiff(
            status="changed",
            version_change=f"{old.version} -> {new.version}",
            added_non_negotiables=set(new.non_negotiables) - set(old.non_negotiables),
            removed_non_negotiables=set(old.non_negotiables) - set(new.non_negotiables),
            added_commitments=set(new.long_horizon_commitments) - set(old.long_horizon_commitments),
            removed_commitments=(
                set(old.long_horizon_commitments)
                - set(new.long_horizon_commitments)
            ),
            added_anti_values=set(new.anti_values) - set(old.anti_values),
            removed_anti_values=set(old.anti_values) - set(new.anti_values),
            added_adversaries=set(new.instinct_adversaries) - set(old.instinct_adversaries),
            removed_adversaries=set(old.instinct_adversaries) - set(new.instinct_adversaries),
        )

    def activate(self, anchor: BlueprintAnchor) -> BlueprintAnchor:
        if anchor.confirmed_by_user:
            raise ValueError("Anchor is already confirmed")

        confirmed = BlueprintAnchor(
            version=anchor.version,
            created_at=anchor.created_at,
            confirmed_by_user=True,
            non_negotiables=anchor.non_negotiables,
            long_horizon_commitments=anchor.long_horizon_commitments,
            anti_values=anchor.anti_values,
            instinct_adversaries=anchor.instinct_adversaries,
            source_file=anchor.source_file,
            source_hash=anchor.source_hash,
        )

        current = self.get_current()
        if current:
            history_filename = f"{current.version}_{current.created_at[:10].replace(':', '-')}.json"
            history_path = HISTORY_DIR / history_filename
            history_path.write_text(
                json.dumps(current.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
            )

        CURRENT_ANCHOR_PATH.write_text(
            json.dumps(confirmed.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return confirmed

    def list_history(self) -> List[str]:
        if not HISTORY_DIR.exists():
            return []
        return sorted([f.stem for f in HISTORY_DIR.glob("*.json")])

    def get_history_version(self, version: str) -> Optional[BlueprintAnchor]:
        history_path = HISTORY_DIR / f"{version}.json"
        if not history_path.exists():
            return None
        data = json.loads(history_path.read_text(encoding="utf-8"))
        return BlueprintAnchor.from_dict(data)
