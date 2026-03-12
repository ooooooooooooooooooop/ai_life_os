"""
Memory Store for AI Life OS.

使用 SQLite 存储事件摘要的向量索引,支持语义检索。
退化方案:使用余弦相似度 in-memory 计算。
"""
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.event_sourcing import DATA_DIR

# 数据库路径
MEMORY_DB_PATH = DATA_DIR / "memory.db"
EMBEDDING_DIMENSION = 1536  # OpenAI text-embedding-3-small 维度


class MemoryStore:
    """事件向量索引存储。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or MEMORY_DB_PATH
        self._ensure_db()

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def index_event(self, event: Dict[str, Any]) -> bool:
        """
        将事件文本化后写入索引。

        Args:
            event: 事件字典,包含 event_type, timestamp, data 等字段

        Returns:
            是否成功写入
        """
        event_id = event.get("timestamp", "")
        event_type = event.get("event_type", "unknown")
        timestamp = event.get("timestamp", "")

        # 将事件转换为可搜索的文本
        text = self._event_to_text(event)

        # 获取 embedding
        embedding = self.get_embedding(text)
        if not embedding:
            print(f"[MemoryStore] 无法获取 embedding: {event_id}")
            return False

        # 存储到数据库
        return self._store_embedding(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            text=text,
            embedding=embedding,
            metadata=event.get("data", {})
        )

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        语义搜索,返回最相关事件。

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            匹配的事件列表,每项包含 event_id, text, score, metadata
        """
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            print("[MemoryStore] 无法获取查询 embedding")
            return []

        # 从数据库读取所有向量
        all_records = self._load_all_embeddings()
        if not all_records:
            return []

        # 计算余弦相似度
        scored = []
        for record in all_records:
            score = self._cosine_similarity(query_embedding, record["embedding"])
            scored.append({
                "event_id": record["event_id"],
                "event_type": record["event_type"],
                "timestamp": record["timestamp"],
                "text": record["text"],
                "score": score,
                "metadata": record["metadata"]
            })

        # 按相似度排序
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        调用 LLM adapter 获取 embedding。

        Args:
            text: 输入文本

        Returns:
            embedding 向量 (list of float)
        """
        try:
            from core.llm_adapter import get_llm
            llm = get_llm()

            # 检查是否有 get_embedding 方法
            if hasattr(llm, "get_embedding"):
                return llm.get_embedding(text)

            # 退化方案:使用 generate 生成伪 embedding
            # (实际项目中应使用专门的 embedding API)
            print("[MemoryStore] LLM adapter 不支持 embedding,使用退化方案")
            return self._pseudo_embedding(text)

        except Exception as e:
            print(f"[MemoryStore] 获取 embedding 失败: {e}")
            return self._pseudo_embedding(text)

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _ensure_db(self) -> None:
        """确保数据库表存在。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type ON memory_index(event_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memory_index(timestamp)
        """)

        conn.commit()
        conn.close()

    def _store_embedding(
        self,
        event_id: str,
        event_type: str,
        timestamp: str,
        text: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """存储 embedding 到数据库。"""
        try:
            import struct

            # 将 embedding 转为二进制
            embedding_blob = struct.pack(f"{len(embedding)}f", *embedding)
            metadata_json = json.dumps(metadata, ensure_ascii=False)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO memory_index
                (event_id, event_type, timestamp, text, embedding, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event_id, event_type, timestamp, text, embedding_blob, metadata_json))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"[MemoryStore] 存储 embedding 失败: {e}")
            return False

    def _load_all_embeddings(self) -> List[Dict[str, Any]]:
        """从数据库加载所有 embedding。"""
        try:
            import struct

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT event_id, event_type, timestamp, text, embedding, metadata
                FROM memory_index
                ORDER BY timestamp DESC
            """)

            records = []
            for row in cursor.fetchall():
                event_id, event_type, timestamp, text, embedding_blob, metadata_json = row

                # 解析 embedding
                embedding = list(struct.unpack(f"{len(embedding_blob)//4}f", embedding_blob))
                metadata = json.loads(metadata_json) if metadata_json else {}

                records.append({
                    "event_id": event_id,
                    "event_type": event_type,
                    "timestamp": timestamp,
                    "text": text,
                    "embedding": embedding,
                    "metadata": metadata
                })

            conn.close()
            return records

        except Exception as e:
            print(f"[MemoryStore] 加载 embedding 失败: {e}")
            return []

    def _event_to_text(self, event: Dict[str, Any]) -> str:
        """将事件转换为可搜索的文本。"""
        parts = []

        event_type = event.get("event_type", "")
        parts.append(f"事件类型: {event_type}")

        timestamp = event.get("timestamp", "")
        if timestamp:
            parts.append(f"时间: {timestamp}")

        data = event.get("data", {})
        if data:
            # 提取关键信息
            if "content" in data:
                parts.append(f"内容: {data['content']}")
            if "task_name" in data:
                parts.append(f"任务: {data['task_name']}")
            if "goal_name" in data:
                parts.append(f"目标: {data['goal_name']}")
            if "action" in data:
                parts.append(f"动作: {data['action']}")
            if "reason" in data:
                parts.append(f"原因: {data['reason']}")

        return " | ".join(parts)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度。"""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _pseudo_embedding(self, text: str) -> List[float]:
        """
        退化方案:生成伪 embedding。
        基于字符分布的 TF 向量,能区分不同文本。
        """
        # 初始化向量
        embedding = [0.0] * EMBEDDING_DIMENSION

        if not text:
            return embedding

        # 基于字符 ord 值的加权分布
        for char in text:
            # 将字符映射到向量维度
            char_value = ord(char)

            # 使用多个维度表示每个字符,增加区分度
            for offset in range(3):
                idx = (char_value * (offset + 1)) % EMBEDDING_DIMENSION
                # 使用高斯分布增加区分度
                weight = 1.0 / (offset + 1)
                embedding[idx] += weight

        # 考虑字符位置信息
        for i, char in enumerate(text):
            pos_weight = 1.0 / (i + 1)
            idx = (ord(char) + i) % EMBEDDING_DIMENSION
            embedding[idx] += pos_weight * 0.5

        # 归一化向量
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding


# 单例实例
_memory_store_instance: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """获取 MemoryStore 单例实例。"""
    global _memory_store_instance
    if _memory_store_instance is None:
        _memory_store_instance = MemoryStore()
    return _memory_store_instance
