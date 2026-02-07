"""
Rule Evaluator for AI Life OS.

配置驱动的规则评估器，替代硬编码的 if-else 逻辑。
支持运行时热加载，无需重启即可更新规则。
"""
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class RuleEvaluator:
    """
    配置驱动的规则评估器，支持热加载。
    
    使用单例模式确保规则配置在应用中共享。
    """
    
    _instance: Optional['RuleEvaluator'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'RuleEvaluator':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config_path = Path(__file__).parent.parent / "config" / "phase_rules.yaml"
        self._rules: Dict[str, Any] = {}
        self._last_mtime: float = 0
        self._load_rules()
        self._start_watcher()
    
    def _load_rules(self) -> None:
        """加载规则配置文件。"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._rules = yaml.safe_load(f) or {}
                self._last_mtime = self._config_path.stat().st_mtime
                print(f"[RuleEvaluator] Loaded rules from {self._config_path}")
            else:
                self._rules = {}
                print(f"[RuleEvaluator] No rules file found at {self._config_path}, using defaults")
        except Exception as e:
            print(f"[RuleEvaluator] Failed to load rules: {e}")
            self._rules = {}
    
    def _start_watcher(self) -> None:
        """启动配置文件监视器（热加载）。"""
        if not self._rules.get("hot_reload", False):
            return
        
        def watch():
            while True:
                time.sleep(2)  # 每 2 秒检查一次（经验值，可调整）
                try:
                    if self._config_path.exists():
                        current_mtime = self._config_path.stat().st_mtime
                        if current_mtime > self._last_mtime:
                            self._load_rules()
                except Exception:
                    pass  # 静默忽略监视错误
        
        watcher_thread = threading.Thread(target=watch, daemon=True)
        watcher_thread.start()
        print("[RuleEvaluator] Hot reload watcher started")
    
    def filter_actions(
        self, 
        phase: str, 
        actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        根据当前 Phase 过滤 Actions。
        
        Args:
            phase: 当前能量阶段 (deep_work, logistics, activation, leisure, connection)
            actions: 待过滤的 Action 列表
            
        Returns:
            过滤后的 Action 列表
            
        注意：
            - 如果无规则配置，默认全部通过
            - 紧急任务可通过 exceptions.emergency_keywords 绕过过滤
        """
        phase_rules = self._rules.get("phases", {}).get(phase, {})
        
        if not phase_rules:
            # Fallback: 无规则时全部通过
            return actions
        
        allow_list = phase_rules.get("allow", [])
        block_list = phase_rules.get("block", [])
        exceptions = phase_rules.get("exceptions", {})
        emergency_keywords = exceptions.get("emergency_keywords", [])
        
        filtered = []
        for action in actions:
            priority = action.get("priority", "substrate_task")
            description = action.get("description", "")
            
            # 紧急情况检查（例外通道）
            is_emergency = any(kw in description for kw in emergency_keywords)
            if is_emergency:
                filtered.append(action)
                continue
            
            # 标准过滤逻辑
            if allow_list == "all":
                # 允许全部
                filtered.append(action)
            elif block_list == "all_except_allowed":
                # 严格白名单模式：仅允许 allow_list 中的优先级
                if priority in allow_list:
                    filtered.append(action)
            elif priority not in block_list:
                # 标准模式：不在黑名单中即通过
                filtered.append(action)
        
        return filtered
    
    def get_phase_description(self, phase: str) -> str:
        """获取阶段描述（用于日志/调试）。"""
        phase_rules = self._rules.get("phases", {}).get(phase, {})
        return phase_rules.get("description", f"Unknown phase: {phase}")
