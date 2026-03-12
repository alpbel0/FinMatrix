"""
SQLAlchemy ORM models for FinMatrix.

This package contains all database models. Import Base from database
and re-export for convenience in migrations and other modules.

Models are organized by domain:
- user.py: users, telegram_settings
- stock.py: stocks
- watchlist.py: watchlist
- enums.py: PeriodType, SyncStatus, NewsSource, MessageRole, MessageType, EmbeddingStatus
- stock_price.py: stock_prices (partitioned)
- balance_sheet.py: balance_sheets
- income_statement.py: income_statements
- cash_flow.py: cash_flows
- kap_report.py: kap_reports
- news.py: news, user_news
- chat.py: chat_sessions, chat_messages
- document_chunk.py: document_chunks
- pipeline_log.py: pipeline_logs
- eval_log.py: eval_logs
"""

from app.database import Base
from app.models.balance_sheet import BalanceSheet
from app.models.cash_flow import CashFlow
from app.models.chat import ChatMessage, ChatSession
from app.models.document_chunk import DocumentChunk
from app.models.enums import (
    EmbeddingStatus,
    MessageRole,
    MessageType,
    NewsSource,
    PeriodType,
    SyncStatus,
)
from app.models.income_statement import IncomeStatement
from app.models.kap_report import KAPReport
from app.models.news import News, UserNews
from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.models.user import TelegramSettings, User
from app.models.watchlist import Watchlist

__all__ = [
    "Base",
    "User",
    "TelegramSettings",
    "Stock",
    "Watchlist",
    "StockPrice",
    "BalanceSheet",
    "IncomeStatement",
    "CashFlow",
    "KAPReport",
    "News",
    "UserNews",
    "ChatSession",
    "ChatMessage",
    "DocumentChunk",
    "PeriodType",
    "SyncStatus",
    "NewsSource",
    "MessageRole",
    "MessageType",
    "EmbeddingStatus",
]