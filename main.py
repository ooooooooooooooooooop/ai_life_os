import os
import sys
from pathlib import Path

import uvicorn

from core.logger import setup_logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Main entry point for AI Life OS Web Service."""
    setup_logging()

    reload_enabled = os.getenv("AI_LIFE_OS_RELOAD", "0").lower() in {"1", "true", "yes"}
    host = os.getenv("AI_LIFE_OS_HOST", "0.0.0.0")
    port = int(os.getenv("AI_LIFE_OS_PORT", "8010"))

    uvicorn.run(
        "web.backend.app:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=["web", "core"] if reload_enabled else None,
    )


if __name__ == "__main__":
    main()
