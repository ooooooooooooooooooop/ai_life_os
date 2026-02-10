import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web.backend.routers import api, goals, onboarding, tasks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


def create_app() -> FastAPI:
    app = FastAPI(title="AI Life OS API", version="2.0")

    raw_origins = os.getenv("AI_LIFE_OS_ALLOWED_ORIGINS", "*")
    allow_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    allow_credentials = "*" not in allow_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "AI Life OS"}

    app.include_router(api.router, prefix="/api/v1", tags=["api"])
    app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["onboarding"])
    app.include_router(goals.router, prefix="/api/v1/goals", tags=["goals"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])

    frontend_dist = Path(__file__).parent.parent / "client" / "dist"
    logger.info("Looking for frontend at: %s", frontend_dist.absolute())

    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        logger.info("Frontend found, serving static files from %s", frontend_dist)
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
    else:
        logger.warning("Frontend dist not found at %s. Running in API-only mode.", frontend_dist)

        @app.get("/")
        async def root():
            return {
                "message": "AI Life OS API is running",
                "docs": "/docs",
                "health": "/health",
                "note": "Frontend not built. Run: cd web/client && npm run build",
            }

    return app


app = create_app()
