import os
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep tests deterministic: no background watcher threads.
os.environ.setdefault("AI_LIFE_OS_DISABLE_WATCHERS", "1")


@pytest.fixture
def clear_goal_registry_singleton():
    """
    清除GoalRegistry单例，确保测试有干净的环境。
    需要显式使用此fixture。
    """
    from core.objective_engine.registry import clear_registry
    clear_registry()
    yield
    clear_registry()
