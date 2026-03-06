"""
配置缓存模块

实现基于文件修改时间的配置缓存机制，减少重复的YAML文件加载。
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class ConfigCache:
    """配置缓存类，基于文件修改时间实现缓存失效机制。"""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}

    def get(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """
        获取缓存的配置数据。

        Args:
            config_path: 配置文件路径

        Returns:
            缓存的配置数据，如果缓存失效或不存在则返回None
        """
        path_str = str(config_path)

        # 检查缓存是否存在
        if path_str not in self._cache:
            return None

        # 检查文件是否被修改
        if not config_path.exists():
            # 文件不存在，清除缓存
            self._cache.pop(path_str, None)
            self._timestamps.pop(path_str, None)
            return None

        current_mtime = config_path.stat().st_mtime
        cached_mtime = self._timestamps.get(path_str, 0)

        if current_mtime > cached_mtime:
            # 文件已被修改，缓存失效
            self._cache.pop(path_str, None)
            self._timestamps.pop(path_str, None)
            return None

        return self._cache[path_str]

    def set(self, config_path: Path, data: Dict[str, Any]) -> None:
        """
        设置配置缓存。

        Args:
            config_path: 配置文件路径
            data: 配置数据
        """
        path_str = str(config_path)

        if not config_path.exists():
            return

        self._cache[path_str] = data
        self._timestamps[path_str] = config_path.stat().st_mtime

    def clear(self, config_path: Optional[Path] = None) -> None:
        """
        清除缓存。

        Args:
            config_path: 指定要清除的配置文件路径，如果为None则清除所有缓存
        """
        if config_path is None:
            self._cache.clear()
            self._timestamps.clear()
        else:
            path_str = str(config_path)
            self._cache.pop(path_str, None)
            self._timestamps.pop(path_str, None)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息。

        Returns:
            缓存统计信息
        """
        return {
            "cache_size": len(self._cache),
            "cached_files": list(self._cache.keys()),
            "timestamps": dict(self._timestamps),
        }


# 全局配置缓存实例
_config_cache = ConfigCache()


def load_yaml_with_cache(config_path: Path) -> Dict[str, Any]:
    """
    使用缓存加载YAML配置文件。

    Args:
        config_path: 配置文件路径

    Returns:
        配置数据
    """
    # 尝试从缓存获取
    cached_data = _config_cache.get(config_path)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，加载文件
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            return {}

        # 存入缓存
        _config_cache.set(config_path, data)
        return data
    except Exception:
        return {}


def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息。

    Returns:
        缓存统计信息
    """
    return _config_cache.get_stats()


def clear_cache(config_path: Optional[Path] = None) -> None:
    """
    清除缓存。

    Args:
        config_path: 指定要清除的配置文件路径，如果为None则清除所有缓存
    """
    _config_cache.clear(config_path)
