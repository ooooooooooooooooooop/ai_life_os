import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep tests deterministic: no background watcher threads.
os.environ.setdefault("AI_LIFE_OS_DISABLE_WATCHERS", "1")
