"""
SQLAlchemy ORM models for FinMatrix.

This package contains all database models. Import Base from database
and re-export for convenience in migrations and other modules.

Models are organized by domain:
- user.py: users, telegram_settings
- stock.py: stocks
- watchlist.py: watchlist
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
from app.models.user import TelegramSettings, User

__all__ = ["Base", "User", "TelegramSettings"]