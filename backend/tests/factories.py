"""
Factory Boy factories for test data generation.

Factory Boy is sync by default, but we can use it with async SQLAlchemy
by using the build() strategy and manually saving objects in async context.

Usage with async SQLAlchemy:
    # Option 1: Build + Manual Save
    user = UserFactory.build()
    async with session.begin():
        session.add(user)
    return user

    # Option 2: Async helper (recommended)
    user = await create_user_async(session, username="testuser")
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any, Optional
import uuid
import hashlib

import factory
from factory.alchemy import SQLAlchemyModelFactory

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


class BaseFactory(SQLAlchemyModelFactory):
    """
    Base factory for all SQLAlchemy model factories.
    """

    class Meta:
        sqlalchemy_session = None  # Will be set in tests
        sqlalchemy_session_persistence = "commit"  # Auto-commit on create


# --- User Factories ---

class UserFactory(BaseFactory):
    """Factory for User model."""

    class Meta:
        model = User

    id = factory.Sequence(lambda n: n + 1)
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password_hash = factory.LazyFunction(
        lambda: "$2b$12$testhashedpasswordfortestpurposesonly"
    )
    telegram_chat_id = None
    notification_enabled = False
    created_at = None
    updated_at = None


class TelegramSettingsFactory(BaseFactory):
    """Factory for TelegramSettings model."""

    class Meta:
        model = TelegramSettings

    user_id = None
    notification_times = factory.LazyFunction(lambda: {"morning": "09:00", "evening": "18:00"})
    event_types = factory.LazyFunction(lambda: {"price_alert": True, "news": True})


# --- Stock Factories ---

class StockFactory(BaseFactory):
    """Factory for Stock model."""

    class Meta:
        model = Stock

    id = factory.Sequence(lambda n: n + 1)
    symbol = factory.Sequence(lambda n: f"TEST{n}")
    yfinance_symbol = factory.Sequence(lambda n: f"TEST{n}.IS")
    company_name = factory.Sequence(lambda n: f"Test Company {n}")
    sector = "Technology"
    exchange = "BIST"
    is_active = True
    created_at = None


class WatchlistFactory(BaseFactory):
    """Factory for Watchlist model."""

    class Meta:
        model = Watchlist

    user_id = None
    stock_id = None
    added_at = None
    notification_enabled = False


class StockPriceFactory(BaseFactory):
    """Factory for StockPrice model."""

    class Meta:
        model = StockPrice

    stock_id = None
    # Use timezone-aware datetime for PostgreSQL TIMESTAMPTZ
    timestamp = factory.LazyFunction(lambda: datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    open = factory.LazyFunction(lambda: Decimal("100.0000"))
    high = factory.LazyFunction(lambda: Decimal("105.0000"))
    low = factory.LazyFunction(lambda: Decimal("98.0000"))
    close = factory.LazyFunction(lambda: Decimal("102.5000"))
    volume = factory.LazyFunction(lambda: 1000000)


# --- Financial Statement Factories ---

class BalanceSheetFactory(BaseFactory):
    """Factory for BalanceSheet model."""

    class Meta:
        model = BalanceSheet

    id = factory.Sequence(lambda n: n + 1)
    stock_id = None
    period = PeriodType.Q1
    date = factory.LazyFunction(lambda: date.today())
    fiscal_year = factory.LazyFunction(lambda: date.today().year)
    fiscal_quarter = 1
    total_assets = factory.LazyFunction(lambda: Decimal("1000000.00"))
    total_liabilities = factory.LazyFunction(lambda: Decimal("500000.00"))
    equity = factory.LazyFunction(lambda: Decimal("500000.00"))
    cash = factory.LazyFunction(lambda: Decimal("100000.00"))
    total_debt = factory.LazyFunction(lambda: Decimal("200000.00"))


class IncomeStatementFactory(BaseFactory):
    """Factory for IncomeStatement model."""

    class Meta:
        model = IncomeStatement

    id = factory.Sequence(lambda n: n + 1)
    stock_id = None
    period = PeriodType.Q1
    date = factory.LazyFunction(lambda: date.today())
    fiscal_year = factory.LazyFunction(lambda: date.today().year)
    fiscal_quarter = 1
    revenue = factory.LazyFunction(lambda: Decimal("2000000.00"))
    net_income = factory.LazyFunction(lambda: Decimal("200000.00"))
    operating_income = factory.LazyFunction(lambda: Decimal("300000.00"))
    gross_profit = factory.LazyFunction(lambda: Decimal("800000.00"))
    ebitda = factory.LazyFunction(lambda: Decimal("400000.00"))


class CashFlowFactory(BaseFactory):
    """Factory for CashFlow model."""

    class Meta:
        model = CashFlow

    id = factory.Sequence(lambda n: n + 1)
    stock_id = None
    period = PeriodType.Q1
    date = factory.LazyFunction(lambda: date.today())
    fiscal_year = factory.LazyFunction(lambda: date.today().year)
    fiscal_quarter = 1
    operating_cash_flow = factory.LazyFunction(lambda: Decimal("250000.00"))
    investing_cash_flow = factory.LazyFunction(lambda: Decimal("-100000.00"))
    financing_cash_flow = factory.LazyFunction(lambda: Decimal("-50000.00"))
    free_cash_flow = factory.LazyFunction(lambda: Decimal("150000.00"))


# --- KAP and News Factories ---

class KAPReportFactory(BaseFactory):
    """Factory for KAPReport model."""

    class Meta:
        model = KAPReport

    id = factory.Sequence(lambda n: n + 1)
    stock_id = None
    bildirim_no = factory.Sequence(lambda n: f"BILDIRIM-{n:06d}")
    title = factory.Sequence(lambda n: f"KAP Report Title {n}")
    pdf_url = factory.LazyAttribute(lambda obj: f"https://kap.org.tr/{obj.bildirim_no}.pdf")
    published_date = factory.LazyFunction(lambda: datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    fetched_date = None
    chroma_sync_status = SyncStatus.PENDING
    chunk_count = 0


class NewsFactory(BaseFactory):
    """Factory for News model."""

    class Meta:
        model = News

    id = factory.Sequence(lambda n: n + 1)
    stock_id = None
    title = factory.Sequence(lambda n: f"News Title {n}")
    content = factory.LazyAttribute(lambda obj: f"Content for {obj.title}")
    published_date = factory.LazyFunction(lambda: datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    source_type = NewsSource.KAP_SUMMARY
    source_ref_id = None


class UserNewsFactory(BaseFactory):
    """Factory for UserNews model."""

    class Meta:
        model = UserNews

    user_id = None
    news_id = None
    is_read = False
    read_at = None


# --- Chat Factories ---

class ChatSessionFactory(BaseFactory):
    """Factory for ChatSession model."""

    class Meta:
        model = ChatSession

    id = factory.Sequence(lambda n: n + 1)
    user_id = None
    title = factory.Sequence(lambda n: f"Chat Session {n}")
    created_at = None
    updated_at = None
    last_message_at = None


class ChatMessageFactory(BaseFactory):
    """Factory for ChatMessage model."""

    class Meta:
        model = ChatMessage

    id = factory.Sequence(lambda n: n + 1)
    session_id = None
    role = MessageRole.USER
    content = factory.Sequence(lambda n: f"Message content {n}")
    message_type = MessageType.TEXT
    extra_data = None
    sources = None
    timestamp = None


# --- Document Chunk Factory ---

class DocumentChunkFactory(BaseFactory):
    """Factory for DocumentChunk model."""

    class Meta:
        model = DocumentChunk

    id = factory.Sequence(lambda n: n + 1)
    kap_report_id = None
    chunk_index = factory.Sequence(lambda n: n)
    chunk_text_hash = factory.LazyFunction(
        lambda: hashlib.sha256(b"test chunk content").hexdigest()
    )
    chroma_document_id = None
    embedding_status = EmbeddingStatus.PENDING


# --- Pipeline Log Factory ---

class PipelineLogFactory(BaseFactory):
    """Factory for PipelineLog model."""

    class Meta:
        model = PipelineLog

    id = factory.Sequence(lambda n: n + 1)
    run_id = factory.LazyFunction(uuid.uuid4)
    pipeline_name = "test_pipeline"
    job_name = "test_job"
    step_name = None
    stock_id = None
    status = PipelineStatus.PENDING
    started_at = None
    finished_at = None
    error_message = None
    processed_count = 0
    details = None


# --- Eval Log Factory ---

class EvalLogFactory(BaseFactory):
    """Factory for EvalLog model."""

    class Meta:
        model = EvalLog

    id = factory.Sequence(lambda n: n + 1)
    message_id = None
    pipeline_run_id = None
    bert_score = factory.LazyFunction(lambda: Decimal("0.8500"))
    rouge_score = factory.LazyFunction(lambda: Decimal("0.7500"))
    retrieval_score = factory.LazyFunction(lambda: Decimal("0.9000"))
    judge_model_used = "gemini-flash"
    judge_reason = "Response is accurate and relevant."
    is_hallucinated = False
    retry_count = 0
    source_chunks_used = None
    details = None
    created_at = None


# --- Async Helper Functions ---

async def create_user_async(
    session: Any,
    username: Optional[str] = None,
    email: Optional[str] = None,
    **kwargs
) -> User:
    """Create and persist a User instance asynchronously."""
    factory_kwargs = kwargs.copy()
    if username is not None:
        factory_kwargs['username'] = username
    if email is not None:
        factory_kwargs['email'] = email
    user = UserFactory.build(**factory_kwargs)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def create_stock_async(
    session: Any,
    symbol: Optional[str] = None,
    yfinance_symbol: Optional[str] = None,
    **kwargs
) -> Stock:
    """Create and persist a Stock instance asynchronously."""
    factory_kwargs = kwargs.copy()
    if symbol is not None:
        factory_kwargs['symbol'] = symbol
    if yfinance_symbol is not None:
        factory_kwargs['yfinance_symbol'] = yfinance_symbol
    stock = StockFactory.build(**factory_kwargs)
    session.add(stock)
    await session.flush()
    await session.refresh(stock)
    return stock


async def create_chat_session_async(
    session: Any,
    user_id: int,
    title: Optional[str] = None,
    **kwargs
) -> ChatSession:
    """Create and persist a ChatSession instance asynchronously."""
    factory_kwargs = kwargs.copy()
    factory_kwargs['user_id'] = user_id
    if title is not None:
        factory_kwargs['title'] = title
    chat_session = ChatSessionFactory.build(**factory_kwargs)
    session.add(chat_session)
    await session.flush()
    await session.refresh(chat_session)
    return chat_session


async def create_kap_report_async(
    session: Any,
    stock_id: int,
    bildirim_no: Optional[str] = None,
    **kwargs
) -> KAPReport:
    """Create and persist a KAPReport instance asynchronously."""
    factory_kwargs = kwargs.copy()
    factory_kwargs['stock_id'] = stock_id
    if bildirim_no is not None:
        factory_kwargs['bildirim_no'] = bildirim_no
    kap_report = KAPReportFactory.build(**factory_kwargs)
    session.add(kap_report)
    await session.flush()
    await session.refresh(kap_report)
    return kap_report


async def create_pipeline_log_async(
    session: Any,
    pipeline_name: str = "test_pipeline",
    **kwargs
) -> PipelineLog:
    """Create and persist a PipelineLog instance asynchronously."""
    factory_kwargs = kwargs.copy()
    factory_kwargs['pipeline_name'] = pipeline_name
    pipeline_log = PipelineLogFactory.build(**factory_kwargs)
    session.add(pipeline_log)
    await session.flush()
    await session.refresh(pipeline_log)
    return pipeline_log
