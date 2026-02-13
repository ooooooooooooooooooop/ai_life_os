#!/usr/bin/env python3
"""
Task Lifecycle Manager for unified-taskflow v3.0

Manages task lifecycle: new, complete, abandon, resume, list, status.

Usage:
    python task-lifecycle.py new <task-name>
    python task-lifecycle.py complete [--message "completion note"]
    python task-lifecycle.py abandon [--reason "reason"]
    python task-lifecycle.py resume <archive-name>
    python task-lifecycle.py list [--active|--archive]
    python task-lifecycle.py status
"""

import json
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


TASKFLOW_DIR = ".taskflow"
ACTIVE_DIR = "active"
ARCHIVE_DIR = "archive"
INDEX_FILE = "index.json"


def get_taskflow_root(project_path: str = ".") -> Path:
    """Get the .taskflow directory path."""
    return Path(project_path).resolve() / TASKFLOW_DIR


def ensure_structure(root: Path) -> None:
    """Ensure .taskflow directory structure exists."""
    (root / ACTIVE_DIR).mkdir(parents=True, exist_ok=True)
    (root / ARCHIVE_DIR).mkdir(parents=True, exist_ok=True)

    index_path = root / INDEX_FILE
    if not index_path.exists():
        index_path.write_text(json.dumps({
            "version": "3.0",
            "tasks": []
        }, indent=2, ensure_ascii=False), encoding='utf-8')


def load_index(root: Path) -> Dict:
    """Load task index."""
    index_path = root / INDEX_FILE
    if index_path.exists():
        return json.loads(index_path.read_text(encoding='utf-8'))
    return {"version": "3.0", "tasks": []}


def save_index(root: Path, index: Dict) -> None:
    """Save task index."""
    index_path = root / INDEX_FILE
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')


def get_active_task(root: Path) -> Optional[str]:
    """Get current active task name, if any."""
    active_dir = root / ACTIVE_DIR
    subdirs = [d for d in active_dir.iterdir() if d.is_dir()]
    if subdirs:
        return subdirs[0].name
    return None


def get_next_version(index: Dict, task_name: str) -> int:
    """Get next version number for a task."""
    versions = [t.get("version", 1) for t in index["tasks"] if t["name"] == task_name]
    return max(versions, default=0) + 1


def new_task(task_name: str) -> bool:
    """Create a new task with anchor.md and checkpoint.md."""
    root = get_taskflow_root()
    ensure_structure(root)

    active = get_active_task(root)
    if active:
        print(f"错误：已有活跃任务 '{active}'")
        print("   请先完成或归档当前任务：")
        print(f"   python task-lifecycle.py complete")
        print(f"   python task-lifecycle.py abandon")
        return False

    task_dir = root / ACTIVE_DIR / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Create anchor.md
    (task_dir / "anchor.md").write_text(
        "# Grounding Anchor\n\n"
        "**Intent**: \n\n"
        "**Constraints**:\n- \n\n"
        "**Scope**:\n- Include: \n- Exclude: \n\n"
        "**Done-when**:\n- \n\n"
        "**Resolved Ambiguities**:\n- \n",
        encoding='utf-8'
    )

    # Create checkpoint.md
    (task_dir / "checkpoint.md").write_text(
        "# 校验点记录\n\n"
        "## Trace Stub\n\n"
        "**目标**：\n**当前假设**：\n**已排除**：\n\n"
        "---\n\n"
        "## 校验点日志\n\n"
        "## Re-grounding 记录\n\n"
        "| 时间 | 对齐 | 说明 | 动作 |\n"
        "|------|------|------|------|\n\n"
        "## Debug 记录\n\n"
        "| 问题 | Strike | 尝试方案 | 结果 |\n"
        "|------|--------|----------|------|\n",
        encoding='utf-8'
    )

    # Update index
    index = load_index(root)
    version = get_next_version(index, task_name)
    index["tasks"].append({
        "name": task_name,
        "version": version,
        "status": "active",
        "created": datetime.now().isoformat(),
        "completed": None
    })
    save_index(root, index)

    print(f"已创建任务 '{task_name}'")
    print(f"   目录: {task_dir}")
    print(f"   文件: anchor.md, checkpoint.md")
    return True


def complete_task(message: str = "") -> bool:
    """Complete and archive the active task."""
    root = get_taskflow_root()
    ensure_structure(root)

    active = get_active_task(root)
    if not active:
        print("错误：没有活跃任务")
        return False

    index = load_index(root)
    task_entry = next((t for t in index["tasks"] if t["name"] == active and t["status"] == "active"), None)

    if not task_entry:
        print("错误：索引不一致")
        return False

    # Generate archive name
    date_str = datetime.now().strftime("%Y-%m-%d")
    version = task_entry.get("version", 1)
    archive_name = f"{date_str}_{active}_v{version}"

    # Move to archive
    src = root / ACTIVE_DIR / active
    dst = root / ARCHIVE_DIR / archive_name
    shutil.move(str(src), str(dst))

    # Add completion note if provided
    if message:
        (dst / "COMPLETED.md").write_text(f"# 完成说明\n\n{message}\n", encoding='utf-8')

    # Update index
    task_entry["status"] = "completed"
    task_entry["completed"] = datetime.now().isoformat()
    task_entry["archive_path"] = archive_name
    save_index(root, index)

    print(f"已归档任务 '{active}'")
    print(f"   归档路径: {dst}")
    return True


def abandon_task(reason: str = "") -> bool:
    """Abandon and archive the active task."""
    root = get_taskflow_root()
    ensure_structure(root)

    active = get_active_task(root)
    if not active:
        print("错误：没有活跃任务")
        return False

    index = load_index(root)
    task_entry = next((t for t in index["tasks"] if t["name"] == active and t["status"] == "active"), None)

    if not task_entry:
        print("错误：索引不一致")
        return False

    # Generate archive name
    date_str = datetime.now().strftime("%Y-%m-%d")
    version = task_entry.get("version", 1)
    archive_name = f"{date_str}_{active}_v{version}_ABANDONED"

    # Move to archive
    src = root / ACTIVE_DIR / active
    dst = root / ARCHIVE_DIR / archive_name
    shutil.move(str(src), str(dst))

    # Add abandonment note
    (dst / "ABANDONED.md").write_text(f"# 放弃说明\n\n{reason or '无'}\n", encoding='utf-8')

    # Update index
    task_entry["status"] = "abandoned"
    task_entry["completed"] = datetime.now().isoformat()
    task_entry["archive_path"] = archive_name
    save_index(root, index)

    print(f"已放弃任务 '{active}'")
    print(f"   归档路径: {dst}")
    return True


def list_tasks(show_active: bool = True, show_archive: bool = True) -> None:
    """List tasks."""
    root = get_taskflow_root()
    ensure_structure(root)

    index = load_index(root)

    if show_active:
        active = get_active_task(root)
        print("活跃任务:")
        if active:
            entry = next((t for t in index["tasks"] if t["name"] == active and t["status"] == "active"), {})
            created = entry.get("created", "unknown")[:10]
            print(f"   {active} (创建: {created})")
        else:
            print("   (无)")

    if show_archive:
        print("\n归档任务:")
        archived = [t for t in index["tasks"] if t["status"] in ("completed", "abandoned")]
        if archived:
            for t in archived[-10:]:  # Show last 10
                status = "[完成]" if t["status"] == "completed" else "[放弃]"
                print(f"   {status} {t.get('archive_path', t['name'])}")
        else:
            print("   (无)")


def show_status() -> None:
    """Show current status."""
    root = get_taskflow_root()

    if not root.exists():
        print("未初始化 .taskflow 目录")
        print("   运行 'python task-lifecycle.py new <task-name>' 开始")
        return

    active = get_active_task(root)
    index = load_index(root)

    print(f"目录: {root}")
    print(f"活跃任务: {active or '(无)'}")
    print(f"归档数量: {len([t for t in index['tasks'] if t['status'] != 'active'])}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    if action == "new":
        if len(sys.argv) < 3:
            print("用法: python task-lifecycle.py new <task-name>")
            sys.exit(1)
        task_name = sys.argv[2]
        success = new_task(task_name)
        sys.exit(0 if success else 1)

    elif action == "complete":
        message = ""
        if "--message" in sys.argv:
            idx = sys.argv.index("--message")
            if idx + 1 < len(sys.argv):
                message = sys.argv[idx + 1]
        success = complete_task(message)
        sys.exit(0 if success else 1)

    elif action == "abandon":
        reason = ""
        if "--reason" in sys.argv:
            idx = sys.argv.index("--reason")
            if idx + 1 < len(sys.argv):
                reason = sys.argv[idx + 1]
        success = abandon_task(reason)
        sys.exit(0 if success else 1)

    elif action == "list":
        show_active = "--archive" not in sys.argv
        show_archive = "--active" not in sys.argv
        list_tasks(show_active, show_archive)

    elif action == "status":
        show_status()

    else:
        print(f"未知操作: {action}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
