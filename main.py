import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
import uvicorn
from core.logger import setup_logging

def main():
    """Main entry point for AI Life OS Web Service."""
    setup_logging()
    
    # 启动 FastAPI 服务
    # 注意：app.py 之后会被重构，这里预留
    uvicorn.run("web.backend.app:app", host="0.0.0.0", port=8010, reload=True, reload_dirs=["web", "core"])

if __name__ == "__main__":
    main()
