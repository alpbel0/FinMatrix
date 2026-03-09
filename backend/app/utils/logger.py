"""Structured logging configuration using loguru."""

import sys
from loguru import logger

from app.config import settings


def setup_logging():
    """Configure loguru for structured logging."""
    logger.remove()  # Remove default handler

    # Console handler with color
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File handler for errors (optional in production)
    if not settings.debug:
        logger.add(
            "logs/error.log",
            level="ERROR",
            rotation="10 MB",
            retention="7 days",
            compression="gz",
        )


def get_logger(name: str):
    """Get a logger instance with context."""
    return logger.bind(name=name)