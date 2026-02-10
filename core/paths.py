"""
Centralized filesystem paths for runtime data.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def get_data_dir() -> Path:
    """
    Return runtime data directory.

    Priority:
    1. AI_LIFE_OS_DATA_DIR env var
    2. <project_root>/data
    """
    raw = os.getenv("AI_LIFE_OS_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return PROJECT_ROOT / "data"


DATA_DIR = get_data_dir()
