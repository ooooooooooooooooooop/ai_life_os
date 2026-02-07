#!/usr/bin/env python3
"""
Session Catchup Script for unified-taskflow v1.1

Analyzes .taskflow/ directory to recover context from previous sessions.

Usage: python session-catchup.py [project-path]
"""

import json
import sys
import os
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


def load_index(root: Path) -> Dict:
    """Load task index."""
    index_path = root / INDEX_FILE
    if index_path.exists():
        return json.loads(index_path.read_text(encoding='utf-8'))
    return {"version": "1.1", "tasks": []}


def get_active_task(root: Path) -> Optional[str]:
    """Get current active task name, if any."""
    active_dir = root / ACTIVE_DIR
    if not active_dir.exists():
        return None
    subdirs = [d for d in active_dir.iterdir() if d.is_dir()]
    if subdirs:
        return subdirs[0].name
    return None


def detect_mode(task_dir: Path) -> str:
    """Detect task mode from files."""
    if (task_dir / "requirement.md").exists():
        return "Spec-Driven"
    elif (task_dir / "task_plan.md").exists():
        return "Standard"
    elif (task_dir / "progress.md").exists():
        return "Lite"
    return "Unknown"


def get_file_summary(file_path: Path, max_lines: int = 20) -> str:
    """Get summary of a file's content."""
    if not file_path.exists():
        return "(文件不存在)"
    
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')[:max_lines]
        return '\n'.join(lines)
    except Exception as e:
        return f"(读取失败: {e})"


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    root = get_taskflow_root(project_path)
    
    print(f"\n[unified-taskflow] SESSION CATCHUP")
    print(f"目录: {root}")
    
    if not root.exists():
        print("\nℹ️ 未检测到 .taskflow/ 目录")
        print("   这可能是新项目或首次使用 unified-taskflow")
        print("   可通过以下命令初始化：")
        print("   python scripts/task-lifecycle.py new <task-name>")
        return
    
    # Check active task
    active_task = get_active_task(root)
    
    if active_task:
        task_dir = root / ACTIVE_DIR / active_task
        mode = detect_mode(task_dir)
        index = load_index(root)
        task_entry = next((t for t in index.get("tasks", []) if t.get("name") == active_task and t.get("status") == "active"), {})
        
        print(f"\n📌 发现活跃任务: {active_task}")
        print(f"   模式: {mode}")
        print(f"   创建时间: {task_entry.get('created', 'unknown')[:16]}")
        print(f"   目录: {task_dir}")
        
        # Show key files
        print("\n--- 任务文件 ---")
        files = list(task_dir.glob("*.md"))
        for f in files:
            print(f"\n📄 {f.name}:")
            print(get_file_summary(f, 15))
        
        print("\n--- 建议操作 ---")
        print("1. 阅读以上内容恢复上下文")
        print("2. 继续执行任务")
        print("3. 或运行 'python scripts/task-lifecycle.py complete' 归档")
    
    else:
        print("\n✅ 无活跃任务")
        
        # Show recent archives
        index = load_index(root)
        recent = [t for t in index.get("tasks", []) if t.get("status") in ("completed", "abandoned")][-5:]
        
        if recent:
            print("\n📦 最近归档:")
            for t in recent:
                status_icon = "✅" if t.get("status") == "completed" else "⚠️"
                print(f"   {status_icon} {t.get('archive_path', t.get('name'))}")
        
        print("\n--- 建议操作 ---")
        print("运行 'python scripts/task-lifecycle.py new <task-name>' 开始新任务")


if __name__ == "__main__":
    main()
