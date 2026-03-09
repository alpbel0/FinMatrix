"""FastAPI application entry point for FinMatrix API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import (
    auth_router,
    chat_router,
    news_router,
    stocks_router,
    watchlist_router,
)
from app.utils.exceptions import AuthError, ExternalAPIError, FinMatrixError, NotFoundError
from app.utils.logger import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Stock Analysis Platform for BIST Investors",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception Handlers ---


@app.exception_handler(FinMatrixError)
async def finmatrix_error_handler(request: Request, exc: FinMatrixError):
    """Handle all FinMatrix custom errors."""
    logger.error(f"FinMatrixError: {exc.message}", extra=exc.details)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": exc.message, "details": exc.details},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    """Handle not found errors."""
    logger.warning(f"Not found: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": exc.message, "details": exc.details},
    )


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    """Handle authentication/authorization errors."""
    logger.warning(f"Auth error: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": exc.message, "details": exc.details},
    )


@app.exception_handler(ExternalAPIError)
async def external_api_error_handler(request: Request, exc: ExternalAPIError):
    """Handle external API errors (yfinance, KAP)."""
    logger.error(f"External API error: {exc.message}", extra=exc.details)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": exc.message, "details": exc.details},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation failed", "details": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )


# --- Include Routers ---

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(stocks_router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(watchlist_router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(news_router, prefix="/api/news", tags=["News"])


# --- Health Check Endpoints ---


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "service": "finmatrix-api", "version": settings.app_version}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {"message": "Welcome to FinMatrix API", "docs": "/docs"}