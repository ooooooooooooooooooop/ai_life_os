from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json

# 注意: 实际搜索 API 需要配置 (如 Serper, Google Search API, etc.)
# 此处定义接口，实现可插拔


@dataclass
class MarketInsight:
    """市场洞察"""
    query: str             # 搜索查询
    insight: str           # 提炼后的洞察
    source: str            # 来源 URL (如有)
    relevance: float       # 相关度 0-1


def search_market_trends(
    skill: str,
    location: str = "China",
    limit: int = 3
) -> List[MarketInsight]:
    """
    搜索市场趋势。
    
    搜索策略:
    1. {skill} + job market + {year}
    2. {skill} + salary + remote + {location}
    3. {skill} + career path + 2026
    
    Args:
        skill: 主要技能
        location: 位置
        limit: 查询次数上限
    
    Returns:
        MarketInsight 列表
    """
    insights = []
    
    # 构建查询
    queries = [
        f"{skill} job market trends 2026",
        f"{skill} remote salary USD 2026",
        f"{skill} career growth opportunities {location}"
    ][:limit]
    
    for query in queries:
        result = _execute_search(query)
        if result:
            insights.append(result)
    
    return insights


def _execute_search(query: str) -> Optional[MarketInsight]:
    """
    执行单次搜索。
    
    集成 Serper API (Google Search Wrapper).
    需要环境变量 SERPER_API_KEY.
    """
    import os
    import requests
    from core.logger import get_logger
    
    logger = get_logger("info_sensing")
    api_key = os.getenv("SERPER_API_KEY")
    
    if not api_key:
        logger.warning("SERPER_API_KEY not found. Using mock search results.")
        # Fallback to Mock
        if "python" in query.lower():
            return MarketInsight(
                query=query,
                insight="Python demand is growing in AI/ML sectors (Mock).",
                source="mock_search_engine",
                relevance=0.9
            )
        return None
        
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            organic = data.get("organic", [])
            if organic:
                top_result = organic[0]
                return MarketInsight(
                    query=query,
                    insight=top_result.get("snippet", "No snippet available"),
                    source=top_result.get("link", "unknown source"),
                    relevance=1.0
                )
    except Exception as e:
        logger.error(f"Search API failed: {e}")
        
    return None
