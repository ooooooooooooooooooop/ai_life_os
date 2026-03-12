"""
Memory Indexer for AI Life OS.

监听 data/event_log.jsonl,增量写入 memory_store。
"""
import json
from pathlib import Path
from typing import Dict, Optional

from core.event_sourcing import DATA_DIR, EVENT_LOG_PATH
from core.memory_store import get_memory_store

# 游标文件路径
CURSOR_PATH = DATA_DIR / "memory_cursor.json"


class MemoryIndexer:
    """增量索引器,将事件日志同步到向量存储。"""

    def __init__(self):
        self.store = get_memory_store()
        self.cursor_path = CURSOR_PATH

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def sync(self) -> int:
        """
        读取未索引的事件,调用 index_event。

        Returns:
            新索引的事件数量
        """
        if not EVENT_LOG_PATH.exists():
            return 0

        # 获取已同步的行号
        last_line = self.get_sync_cursor()

        # 读取新事件
        new_events = self._read_events_from_line(last_line + 1)
        if not new_events:
            return 0

        # 索引每个事件
        indexed_count = 0
        for line_num, event in new_events:
            try:
                if self.store.index_event(event):
                    indexed_count += 1
                    # 更新游标
                    self.set_sync_cursor(line_num)
            except Exception as e:
                print(f"[MemoryIndexer] 索引事件失败 (行 {line_num}): {e}")
                continue

        return indexed_count

    def get_sync_cursor(self) -> int:
        """
        获取已同步到哪一行。

        Returns:
            最后同步的行号 (0-based)
        """
        if not self.cursor_path.exists():
            return 0

        try:
            with open(self.cursor_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_line", 0)
        except Exception as e:
            print(f"[MemoryIndexer] 读取游标失败: {e}")
            return 0

    def set_sync_cursor(self, line_num: int) -> None:
        """
        记录已同步到哪一行。

        Args:
            line_num: 行号 (1-based)
        """
        try:
            self.cursor_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cursor_path, "w", encoding="utf-8") as f:
                json.dump({"last_line": line_num}, f)
        except Exception as e:
            print(f"[MemoryIndexer] 写入游标失败: {e}")

    def reset_cursor(self) -> None:
        """重置游标,允许重新索引所有事件。"""
        if self.cursor_path.exists():
            self.cursor_path.unlink()

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _read_events_from_line(self, start_line: int) -> list:
        """
        从指定行开始读取事件。

        Args:
            start_line: 起始行号 (1-based)

        Returns:
            [(line_num, event_dict), ...] 列表
        """
        events = []

        try:
            with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if line_num < start_line:
                        continue

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        events.append((line_num, event))
                    except json.JSONDecodeError as e:
                        print(f"[MemoryIndexer] JSON 解析失败 (行 {line_num}): {e}")
                        continue

        except Exception as e:
            print(f"[MemoryIndexer] 读取事件日志失败: {e}")

        return events


# 单例实例
_indexer_instance: Optional[MemoryIndexer] = None


def get_memory_indexer() -> MemoryIndexer:
    """获取 MemoryIndexer 单例实例。"""
    global _indexer_instance
    if _indexer_instance is None:
        _indexer_instance = MemoryIndexer()
    return _indexer_instance


def sync_memory() -> int:
    """便捷函数:同步事件到内存存储。"""
    return get_memory_indexer().sync()
