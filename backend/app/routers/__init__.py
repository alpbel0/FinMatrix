"""Router exports for FinMatrix API."""

from .auth import router as auth_router
from .chat import router as chat_router
from .news import router as news_router
from .stocks import router as stocks_router
from .watchlist import router as watchlist_router

__all__ = [
    "auth_router",
    "stocks_router",
    "watchlist_router",
    "chat_router",
    "news_router",
]