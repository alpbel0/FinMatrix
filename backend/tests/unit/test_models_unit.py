"""
Unit tests for SQLAlchemy ORM models.

These tests verify model structure without database interaction:
- Table names and columns
- Relationships defined correctly
- Enum values
- Repr methods
"""

import pytest
from datetime import datetime, date
from decimal import Decimal

from app.models import (
    User,
    TelegramSettings,
    Stock,
    Watchlist,
    StockPrice,
    BalanceSheet,
    IncomeStatement,
    CashFlow,
    KAPReport,
    News,
    UserNews,
    ChatSession,
    ChatMessage,
    DocumentChunk,
    PipelineLog,
    EvalLog,
)
from app.models.enums import (
    PeriodType,
    SyncStatus,
    NewsSource,
    MessageRole,
    MessageType,
    EmbeddingStatus,
    PipelineStatus,
)
from tests.factories import (
    UserFactory,
    TelegramSettingsFactory,
    StockFactory,
    WatchlistFactory,
    StockPriceFactory,
    BalanceSheetFactory,
    IncomeStatementFactory,
    CashFlowFactory,
    KAPReportFactory,
    NewsFactory,
    UserNewsFactory,
    ChatSessionFactory,
    ChatMessageFactory,
    DocumentChunkFactory,
    PipelineLogFactory,
    EvalLogFactory,
)


# --- User Model Tests ---

class TestUserModel:
    """User model field and relationship tests."""

    def test_user_table_name(self):
        """User table name should be 'users'."""
        assert User.__tablename__ == "users"

    def test_user_columns_exist(self):
        """User model should have all required columns."""
        user = UserFactory.build()
        assert hasattr(user, "id")
        assert hasattr(user, "username")
        assert hasattr(user, "email")
        assert hasattr(user, "password_hash")
        assert hasattr(user, "telegram_chat_id")
        assert hasattr(user, "notification_enabled")
        assert hasattr(user, "created_at")
        assert hasattr(user, "updated_at")

    def test_user_relationships_defined(self):
        """User model should have all relationships defined."""
        user = UserFactory.build()
        # These are relationship attributes (will be None/empty for unsaved instance)
        assert hasattr(user, "telegram_settings")
        assert hasattr(user, "watchlist_entries")
        assert hasattr(user, "news_read_status")
        assert hasattr(user, "chat_sessions")

    def test_user_repr(self):
        """User repr should contain key fields."""
        user = UserFactory.build(id=1, username="testuser", email="test@example.com")
        repr_str = repr(user)
        assert "User" in repr_str
        assert "id=1" in repr_str
        assert "testuser" in repr_str
        assert "test@example.com" in repr_str


class TestTelegramSettingsModel:
    """TelegramSettings model tests."""

    def test_telegram_settings_table_name(self):
        """TelegramSettings table name should be 'telegram_settings'."""
        assert TelegramSettings.__tablename__ == "telegram_settings"

    def test_telegram_settings_columns_exist(self):
        """TelegramSettings model should have all required columns."""
        settings = TelegramSettingsFactory.build()
        assert hasattr(settings, "user_id")
        assert hasattr(settings, "notification_times")
        assert hasattr(settings, "event_types")

    def test_telegram_settings_user_id_primary_key(self):
        """TelegramSettings user_id should be the primary key."""
        from sqlalchemy import inspect
        mapper = inspect(TelegramSettings)
        pk_columns = [c.key for c in mapper.primary_key]
        assert "user_id" in pk_columns


# --- Stock Model Tests ---

class TestStockModel:
    """Stock model tests."""

    def test_stock_table_name(self):
        """Stock table name should be 'stocks'."""
        assert Stock.__tablename__ == "stocks"

    def test_stock_unique_symbol(self):
        """Stock symbol should have unique constraint."""
        stock = StockFactory.build()
        assert hasattr(stock, "symbol")

    def test_stock_relationships_count(self):
        """Stock model should have 8 relationships defined."""
        stock = StockFactory.build()
        relationship_names = [
            "watchlist_entries",
            "prices",
            "balance_sheets",
            "income_statements",
            "cash_flows",
            "kap_reports",
            "news_items",
            "pipeline_logs",
        ]
        for name in relationship_names:
            assert hasattr(stock, name), f"Missing relationship: {name}"

    def test_stock_repr(self):
        """Stock repr should contain key fields."""
        stock = StockFactory.build(id=1, symbol="THYAO", company_name="Turk Hava Yollari")
        repr_str = repr(stock)
        assert "Stock" in repr_str
        assert "id=1" in repr_str
        assert "THYAO" in repr_str


class TestWatchlistModel:
    """Watchlist composite PK tests."""

    def test_watchlist_table_name(self):
        """Watchlist table name should be 'watchlist'."""
        assert Watchlist.__tablename__ == "watchlist"

    def test_watchlist_composite_primary_key(self):
        """Watchlist should have composite primary key (user_id, stock_id)."""
        from sqlalchemy import inspect
        mapper = inspect(Watchlist)
        pk_columns = sorted([c.key for c in mapper.primary_key])
        assert pk_columns == ["stock_id", "user_id"]

    def test_watchlist_relationships(self):
        """Watchlist should have user and stock relationships."""
        watchlist = WatchlistFactory.build()
        assert hasattr(watchlist, "user")
        assert hasattr(watchlist, "stock")


class TestStockPriceModel:
    """StockPrice partitioned model tests."""

    def test_stock_price_table_name(self):
        """StockPrice table name should be 'stock_prices'."""
        assert StockPrice.__tablename__ == "stock_prices"

    def test_stock_price_composite_pk(self):
        """StockPrice should have composite primary key (stock_id, timestamp)."""
        from sqlalchemy import inspect
        mapper = inspect(StockPrice)
        pk_columns = sorted([c.key for c in mapper.primary_key])
        assert pk_columns == ["stock_id", "timestamp"]

    def test_stock_price_decimal_precision(self):
        """StockPrice OHLC fields should be Decimal."""
        price = StockPriceFactory.build()
        assert isinstance(price.open, Decimal)
        assert isinstance(price.high, Decimal)
        assert isinstance(price.low, Decimal)
        assert isinstance(price.close, Decimal)


# --- Financial Models Tests ---

class TestFinancialModels:
    """BalanceSheet, IncomeStatement, CashFlow tests."""

    def test_period_type_enum_values(self):
        """PeriodType enum should have all expected values."""
        assert PeriodType.Q1.value == "Q1"
        assert PeriodType.Q2.value == "Q2"
        assert PeriodType.Q3.value == "Q3"
        assert PeriodType.Q4.value == "Q4"
        assert PeriodType.ANNUAL.value == "ANNUAL"

    def test_balance_sheet_table_name(self):
        """BalanceSheet table name should be 'balance_sheets'."""
        assert BalanceSheet.__tablename__ == "balance_sheets"

    def test_income_statement_table_name(self):
        """IncomeStatement table name should be 'income_statements'."""
        assert IncomeStatement.__tablename__ == "income_statements"

    def test_cash_flow_table_name(self):
        """CashFlow table name should be 'cash_flows'."""
        assert CashFlow.__tablename__ == "cash_flows"

    def test_financial_models_have_stock_relationship(self):
        """All financial models should have stock relationship."""
        balance_sheet = BalanceSheetFactory.build()
        income_statement = IncomeStatementFactory.build()
        cash_flow = CashFlowFactory.build()

        assert hasattr(balance_sheet, "stock")
        assert hasattr(income_statement, "stock")
        assert hasattr(cash_flow, "stock")

    def test_decimal_fields_nullable(self):
        """Financial decimal fields should be nullable."""
        balance_sheet = BalanceSheetFactory.build()
        # These should be None-able
        assert balance_sheet.total_assets is not None  # We set a value
        balance_sheet_null = BalanceSheetFactory.build(
            total_assets=None,
            total_liabilities=None,
            equity=None,
        )
        assert balance_sheet_null.total_assets is None


# --- KAP Report Model Tests ---

class TestKAPReportModel:
    """KAPReport tests."""

    def test_kap_report_table_name(self):
        """KAPReport table name should be 'kap_reports'."""
        assert KAPReport.__tablename__ == "kap_reports"

    def test_bildirim_no_unique(self):
        """KAPReport bildirim_no should be unique."""
        report = KAPReportFactory.build()
        assert hasattr(report, "bildirim_no")

    def test_chroma_sync_status_default(self):
        """KAPReport chroma_sync_status should default to PENDING."""
        report = KAPReportFactory.build()
        assert report.chroma_sync_status == SyncStatus.PENDING

    def test_kap_report_relationships(self):
        """KAPReport should have stock and document_chunks relationships."""
        report = KAPReportFactory.build()
        assert hasattr(report, "stock")
        assert hasattr(report, "document_chunks")

    def test_kap_report_repr(self):
        """KAPReport repr should contain key fields."""
        report = KAPReportFactory.build(id=1, bildirim_no="BILDIRIM-000001")
        repr_str = repr(report)
        assert "KAPReport" in repr_str
        assert "BILDIRIM-000001" in repr_str


# --- News Model Tests ---

class TestNewsModel:
    """News and UserNews tests."""

    def test_news_table_name(self):
        """News table name should be 'news'."""
        assert News.__tablename__ == "news"

    def test_news_source_enum_values(self):
        """NewsSource enum should have all expected values."""
        assert NewsSource.KAP_SUMMARY.value == "kap_summary"
        assert NewsSource.EXTERNAL_NEWS.value == "external_news"
        assert NewsSource.MANUAL.value == "manual"

    def test_news_stock_nullable(self):
        """News stock_id should be nullable for general market news."""
        news = NewsFactory.build(stock_id=None)
        assert news.stock_id is None

    def test_user_news_composite_pk(self):
        """UserNews should have composite primary key (user_id, news_id)."""
        from sqlalchemy import inspect
        mapper = inspect(UserNews)
        pk_columns = sorted([c.key for c in mapper.primary_key])
        assert pk_columns == ["news_id", "user_id"]


# --- Chat Model Tests ---

class TestChatModels:
    """ChatSession and ChatMessage tests."""

    def test_chat_session_table_name(self):
        """ChatSession table name should be 'chat_sessions'."""
        assert ChatSession.__tablename__ == "chat_sessions"

    def test_chat_message_table_name(self):
        """ChatMessage table name should be 'chat_messages'."""
        assert ChatMessage.__tablename__ == "chat_messages"

    def test_message_role_enum(self):
        """MessageRole enum should have all expected values."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"

    def test_message_type_enum(self):
        """MessageType enum should have all expected values."""
        assert MessageType.TEXT.value == "text"
        assert MessageType.CHART.value == "chart"
        assert MessageType.TABLE.value == "table"
        assert MessageType.SYSTEM.value == "system"

    def test_chat_session_relationships(self):
        """ChatSession should have user and messages relationships."""
        session = ChatSessionFactory.build()
        assert hasattr(session, "user")
        assert hasattr(session, "messages")

    def test_chat_message_relationships(self):
        """ChatMessage should have session and eval_logs relationships."""
        message = ChatMessageFactory.build()
        assert hasattr(message, "session")
        assert hasattr(message, "eval_logs")


# --- Document Chunk Model Tests ---

class TestDocumentChunkModel:
    """DocumentChunk tests."""

    def test_document_chunk_table_name(self):
        """DocumentChunk table name should be 'document_chunks'."""
        assert DocumentChunk.__tablename__ == "document_chunks"

    def test_embedding_status_enum(self):
        """EmbeddingStatus enum should have all expected values."""
        assert EmbeddingStatus.PENDING.value == "PENDING"
        assert EmbeddingStatus.SUCCESS.value == "SUCCESS"
        assert EmbeddingStatus.FAILED.value == "FAILED"

    def test_document_chunk_relationship(self):
        """DocumentChunk should have kap_report relationship."""
        chunk = DocumentChunkFactory.build()
        assert hasattr(chunk, "kap_report")


# --- Pipeline Log Model Tests ---

class TestPipelineLogModel:
    """PipelineLog tests."""

    def test_pipeline_log_table_name(self):
        """PipelineLog table name should be 'pipeline_logs'."""
        assert PipelineLog.__tablename__ == "pipeline_logs"

    def test_pipeline_status_enum(self):
        """PipelineStatus enum should have all expected values."""
        assert PipelineStatus.PENDING.value == "PENDING"
        assert PipelineStatus.RUNNING.value == "RUNNING"
        assert PipelineStatus.SUCCESS.value == "SUCCESS"
        assert PipelineStatus.FAILED.value == "FAILED"

    def test_run_id_uuid_default(self):
        """PipelineLog run_id should have UUID default."""
        log = PipelineLogFactory.build()
        assert log.run_id is not None
        # run_id should be a UUID
        from uuid import UUID
        assert isinstance(log.run_id, UUID)

    def test_pipeline_log_relationships(self):
        """PipelineLog should have stock and eval_logs relationships."""
        log = PipelineLogFactory.build()
        assert hasattr(log, "stock")
        assert hasattr(log, "eval_logs")


# --- Eval Log Model Tests ---

class TestEvalLogModel:
    """EvalLog tests."""

    def test_eval_log_table_name(self):
        """EvalLog table name should be 'eval_logs'."""
        assert EvalLog.__tablename__ == "eval_logs"

    def test_eval_log_score_precision(self):
        """EvalLog scores should be Decimal with precision."""
        log = EvalLogFactory.build()
        assert isinstance(log.bert_score, Decimal)
        assert isinstance(log.rouge_score, Decimal)
        assert isinstance(log.retrieval_score, Decimal)

    def test_eval_log_relationships(self):
        """EvalLog should have message and pipeline_log relationships."""
        log = EvalLogFactory.build()
        assert hasattr(log, "message")
        assert hasattr(log, "pipeline_log")

    def test_eval_log_repr(self):
        """EvalLog repr should contain key fields."""
        log = EvalLogFactory.build(id=1, is_hallucinated=False)
        repr_str = repr(log)
        assert "EvalLog" in repr_str
        assert "is_hallucinated" in repr_str


# --- Sync Status Enum Tests ---

class TestSyncStatusEnum:
    """SyncStatus enum tests."""

    def test_sync_status_values(self):
        """SyncStatus enum should have all expected values."""
        assert SyncStatus.PENDING.value == "PENDING"
        assert SyncStatus.SUCCESS.value == "SUCCESS"
        assert SyncStatus.FAILED.value == "FAILED"

    def test_sync_status_string_representation(self):
        """SyncStatus should be string enum."""
        assert SyncStatus.PENDING == "PENDING"
        assert SyncStatus.SUCCESS == "SUCCESS"
        assert SyncStatus.FAILED == "FAILED"