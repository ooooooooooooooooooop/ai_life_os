"""
Memory API Router for AI Life OS.

提供语义检索接口。
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class SearchResult(BaseModel):
    """搜索结果模型。"""
    event_id: str
    event_type: str
    timestamp: str
    text: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    """搜索响应模型。"""
    query: str
    results: List[SearchResult]
    total: int


@router.get("/search", response_model=SearchResponse)
async def search_memory(
    q: str = Query(..., description="查询文本"),
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量")
):
    """
    语义搜索历史事件。

    Args:
        q: 查询文本,如"最近三周有没有重复跳过晨间任务"
        top_k: 返回结果数量,默认 5

    Returns:
        匹配的事件列表
    """
    try:
        from core.memory_store import get_memory_store

        store = get_memory_store()
        results = store.search(q, top_k)

        search_results = [
            SearchResult(
                event_id=r["event_id"],
                event_type=r["event_type"],
                timestamp=r["timestamp"],
                text=r["text"],
                score=r["score"],
                metadata=r["metadata"]
            )
            for r in results
        ]

        return SearchResponse(
            query=q,
            results=search_results,
            total=len(search_results)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/sync")
async def sync_memory():
    """
    手动触发事件索引同步。

    将 event_log.jsonl 中未索引的事件写入向量存储。
    """
    try:
        from core.memory_indexer import sync_memory as do_sync_memory

        indexed_count = do_sync_memory()

        return {
            "status": "success",
            "indexed_count": indexed_count,
            "message": f"成功索引 {indexed_count} 个事件"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/status")
async def get_memory_status():
    """
    获取内存存储状态。

    返回已索引事件数量、数据库大小等信息。
    """
    try:
        from core.memory_store import MEMORY_DB_PATH, get_memory_store
        import sqlite3

        store = get_memory_store()

        # 统计已索引事件数量
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memory_index")
        event_count = cursor.fetchone()[0]
        conn.close()

        # 数据库文件大小
        db_size = MEMORY_DB_PATH.stat().st_size if MEMORY_DB_PATH.exists() else 0

        return {
            "status": "active",
            "indexed_events": event_count,
            "db_size_bytes": db_size,
            "db_path": str(MEMORY_DB_PATH)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")
