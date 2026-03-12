"""
User Profile Updater
从复盘报告中提取行为数据，更新 config/persona/USER.md
"""
from pathlib import Path
from datetime import datetime
import re

USER_MD_PATH = Path(__file__).parent.parent / "config" / "persona" / "USER.md"


def update_user_profile(report: dict) -> None:
    """
    从复盘报告中提取行为观察数据，写入 USER.md。
    全程 try-except，失败不影响主流程。
    """
    try:
        stats = report.get("statistics", {})
        patterns = report.get("failure_patterns", [])

        updates = {}

        # 1. 实际完成率最高/最低的任务类型
        by_priority = stats.get("by_priority", {})
        completed = [k for k, v in by_priority.items() if v.get("completion_rate", 0) >= 0.7]
        skipped = [k for k, v in by_priority.items() if v.get("completion_rate", 0) < 0.3]
        if completed:
            updates["frequently_completed_types"] = completed
        if skipped:
            updates["frequently_skipped_types"] = skipped

        # 2. 本能劫持模式
        hijack_triggers = [p.get("pattern") for p in patterns if p.get("pattern")]
        if hijack_triggers:
            updates["hijack_triggers"] = hijack_triggers
        updates["hijack_frequency"] = str(len(patterns))

        # 3. 元数据
        updates["last_observed"] = datetime.now().strftime("%Y-%m-%d")
        updates["observation_sample_size"] = report.get("event_count", 0)

        # 4. 写入 USER.md（简单行替换，保留注释格式）
        _patch_user_md(updates)

    except Exception as e:
        print(f"[UserProfileUpdater] 更新失败，跳过: {e}")


def _patch_user_md(updates: dict) -> None:
    """将 updates 中的字段写入 USER.md，替换对应行的值。"""
    if not USER_MD_PATH.exists():
        return
    content = USER_MD_PATH.read_text(encoding="utf-8")
    for key, value in updates.items():
        # 匹配 "key: 任意内容  # 注释" 格式的行
        pattern = rf"^({re.escape(key)}:\s*).*?(#.*)?$"
        replacement = rf"\g<1>{value}  \g<2>" if "#" in content else rf"\g<1>{value}"
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    USER_MD_PATH.write_text(content, encoding="utf-8")
