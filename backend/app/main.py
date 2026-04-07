from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import check_database_connection
from app.routers.auth import router as auth_router
from app.services.utils.logging import logger

settings = get_settings()

app = FastAPI(title="FinMatrix API", description="AI-powered stock analysis for BIST", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    try:
        await check_database_connection()
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        logger.exception("Database health check failed")
        return {"status": "ok", "database": f"error: {exc}"}
