from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import check_database_connection
from app.routers.auth import router as auth_router
from app.routers.stocks import router as stocks_router
from app.routers.admin import router as admin_router
from app.services.pipeline.scheduler import start_scheduler, stop_scheduler
from app.services.utils.logging import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Application starting up...")
    await start_scheduler()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Application shutting down...")
    await stop_scheduler()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="FinMatrix API",
    description="AI-powered stock analysis for BIST",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(stocks_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    try:
        await check_database_connection()
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        logger.exception("Database health check failed")
        return {"status": "ok", "database": f"error: {exc}"}