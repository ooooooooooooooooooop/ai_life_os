"""
Rule Evaluator for AI Life OS.

Config-driven action filtering with optional hot-reload.
"""
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class RuleEvaluator:
    """
    Config-driven rule evaluator with singleton semantics.
    """

    _instance: Optional["RuleEvaluator"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "RuleEvaluator":
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
        """Load rule config file."""
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._rules = yaml.safe_load(f) or {}
                self._last_mtime = self._config_path.stat().st_mtime
                print(f"[RuleEvaluator] Loaded rules from {self._config_path}")
            else:
                self._rules = {}
                print(f"[RuleEvaluator] No rules file found at {self._config_path}, using defaults")
        except Exception as e:
            print(f"[RuleEvaluator] Failed to load rules: {e}")
            self._rules = {}

    def _watchers_disabled(self) -> bool:
        # Keep tests deterministic and avoid long-lived watcher side effects.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        return os.getenv("AI_LIFE_OS_DISABLE_WATCHERS", "0").lower() in {"1", "true", "yes"}

    def _start_watcher(self) -> None:
        """Start hot-reload watcher thread for config changes."""
        if self._watchers_disabled():
            return
        if not self._rules.get("hot_reload", False):
            return

        def watch():
            while True:
                time.sleep(2)
                try:
                    if self._config_path.exists():
                        current_mtime = self._config_path.stat().st_mtime
                        if current_mtime > self._last_mtime:
                            self._load_rules()
                except Exception:
                    pass

        watcher_thread = threading.Thread(target=watch, daemon=True)
        watcher_thread.start()
        print("[RuleEvaluator] Hot reload watcher started")

    def filter_actions(self, phase: str, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter actions according to current phase rules.
        """
        phase_rules = self._rules.get("phases", {}).get(phase, {})
        if not phase_rules:
            return actions

        allow_list = phase_rules.get("allow", [])
        block_list = phase_rules.get("block", [])
        exceptions = phase_rules.get("exceptions", {})
        emergency_keywords = exceptions.get("emergency_keywords", [])

        filtered = []
        for action in actions:
            priority = action.get("priority", "substrate_task")
            description = action.get("description", "")

            if any(kw in description for kw in emergency_keywords):
                filtered.append(action)
                continue

            if allow_list == "all":
                filtered.append(action)
            elif block_list == "all_except_allowed":
                if priority in allow_list:
                    filtered.append(action)
            elif priority not in block_list:
                filtered.append(action)

        return filtered

    def get_phase_description(self, phase: str) -> str:
        """Get phase description for logging/debugging."""
        phase_rules = self._rules.get("phases", {}).get(phase, {})
        return phase_rules.get("description", f"Unknown phase: {phase}")
