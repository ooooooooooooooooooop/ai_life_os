from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

from web.backend.routers import onboarding, goals, tasks, api

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

def create_app() -> FastAPI:
    app = FastAPI(title="AI Life OS API", version="2.0")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有，开发方便
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "AI Life OS"}

    # Include Routers（api 提供 /state、/visions、/goals 确认等，与 goals/tasks 互补）
    app.include_router(api.router, prefix="/api/v1", tags=["api"])
    app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["onboarding"])
    app.include_router(goals.router, prefix="/api/v1/goals", tags=["goals"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])

    # Serve Frontend (Build)
    frontend_dist = Path(__file__).parent.parent / "client" / "dist"
    logger.info(f"Looking for frontend at: {frontend_dist.absolute()}")
    
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        logger.info(f"✅ Frontend found, serving static files from {frontend_dist}")
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
    else:
        logger.warning(f"⚠️ Frontend dist not found at {frontend_dist}. Running in API-only mode.")
        # API-only 模式下提供根路由
        @app.get("/")
        async def root():
            return {
                "message": "AI Life OS API is running",
                "docs": "/docs",
                "health": "/health",
                "note": "前端未构建。请运行: cd web/client && npm run build"
            }

    return app

app = create_app()
