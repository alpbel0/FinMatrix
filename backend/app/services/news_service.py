"""News service for news feed and KAP-to-News transformation."""

from sqlalchemy import desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.news import News, UserNews
from app.models.kap_report import KapReport
from app.models.stock import Stock


# Category mapping from filing_type to UI category
FILING_TYPE_CATEGORY_MAP = {
    "FR": "financial_activity",
    "FAR": "financial_activity",
    "ODA": "kap_disclosures",
    "DG": "kap_disclosures",
}


def derive_category(filing_type: str | None) -> str:
    """
    Derive UI category from raw filing_type.

    Args:
        filing_type: Raw KAP filing type (e.g., "FR", "FAR")

    Returns:
        UI category string: "financial_activity" or "kap_disclosures"
    """
    if filing_type and filing_type in FILING_TYPE_CATEGORY_MAP:
        return FILING_TYPE_CATEGORY_MAP[filing_type]
    return "kap_disclosures"


def _apply_category_filter(query, category: str | None):
    if not category:
        return query
    if category == "financial_activity":
        return query.where(News.filing_type.in_(["FR", "FAR"]))
    if category == "kap_disclosures":
        return query.where(News.filing_type.in_(["ODA", "DG"]))
    return query.where(News.category == category)


async def transform_kap_to_news(db: AsyncSession, kap_report: KapReport) -> News | None:
    """
    Transform a KapReport into a News entry with get-or-create logic.

    Creates a News record with:
    - stock_id from kap_report.stock_id
    - title from kap_report.title
    - source_type = "kap"
    - source_id = kap_report.id
    - filing_type = kap_report.filing_type (raw)
    - category derived from filing_type

    Args:
        db: AsyncSession instance
        kap_report: KapReport model instance

    Returns:
        Created News instance, existing News if duplicate, or None if kap_report.stock_id is None
    """
    if kap_report.stock_id is None:
        return None

    # Check if news already exists for this KAP report (get-or-create)
    existing = await db.execute(
        select(News).where(
            News.source_type == "kap",
            News.source_id == kap_report.id,
        )
    )
    existing_news = existing.scalar_one_or_none()
    if existing_news:
        return existing_news  # Already transformed

    news = News(
        stock_id=kap_report.stock_id,
        title=kap_report.title,
        category=derive_category(kap_report.filing_type),
        excerpt=kap_report.summary,  # Use summary as excerpt
        source_url=kap_report.source_url,
        source_type="kap",
        source_id=kap_report.id,
        filing_type=kap_report.filing_type,
    )
    db.add(news)
    await db.commit()
    await db.refresh(news)
    return news


async def get_news_feed(
    db: AsyncSession,
    user_id: int,
    category: str | None = None,
    stock_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[News]:
    """
    Get news feed for a user with optional filters.

    Args:
        db: AsyncSession instance
        user_id: User ID (unused for now, but kept for future user-specific feeds)
        category: Filter by category ("financial_activity", "kap_disclosures")
        stock_id: Filter by stock ID
        limit: Max items to return
        offset: Pagination offset

    Returns:
        List of News model instances ordered by created_at desc
    """
    query = (
        select(News)
        .options(joinedload(News.stock))
        .order_by(desc(News.created_at))
        .limit(limit)
        .offset(offset)
    )

    query = _apply_category_filter(query, category)

    if stock_id:
        query = query.where(News.stock_id == stock_id)

    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def get_news_detail(db: AsyncSession, news_id: int) -> News | None:
    """
    Get a single news item by ID.

    Args:
        db: AsyncSession instance
        news_id: News ID

    Returns:
        News model instance or None
    """
    result = await db.execute(
        select(News).options(joinedload(News.stock)).where(News.id == news_id)
    )
    return result.unique().scalar_one_or_none()


async def get_user_news_status(db: AsyncSession, user_id: int, news_id: int) -> UserNews | None:
    """
    Get UserNews record for a specific news item.

    Args:
        db: AsyncSession instance
        user_id: User ID
        news_id: News ID

    Returns:
        UserNews model instance or None
    """
    result = await db.execute(
        select(UserNews).where(
            UserNews.user_id == user_id,
            UserNews.news_id == news_id,
        )
    )
    return result.scalar_one_or_none()


async def mark_news_read(db: AsyncSession, user_id: int, news_id: int, is_read: bool = True) -> UserNews:
    """
    Mark a news item as read/unread for a user.

    Creates UserNews record if not exists.

    Args:
        db: AsyncSession instance
        user_id: User ID
        news_id: News ID
        is_read: Read status

    Returns:
        UserNews model instance
    """
    user_news = await get_user_news_status(db, user_id, news_id)

    if user_news:
        user_news.is_read = is_read
    else:
        user_news = UserNews(
            user_id=user_id,
            news_id=news_id,
            is_read=is_read,
        )
        db.add(user_news)

    await db.commit()
    await db.refresh(user_news)
    return user_news


async def get_unread_count(
    db: AsyncSession,
    user_id: int,
    category: str | None = None,
    stock_id: int | None = None,
) -> int:
    """Get count of unread news items for a user with optional filters."""
    total_query = select(func.count()).select_from(News)
    total_query = _apply_category_filter(total_query, category)
    if stock_id:
        total_query = total_query.where(News.stock_id == stock_id)

    total_result = await db.execute(total_query)
    total_count = total_result.scalar() or 0

    read_query = (
        select(func.count(distinct(UserNews.news_id)))
        .select_from(UserNews)
        .join(News, News.id == UserNews.news_id)
        .where(
            UserNews.user_id == user_id,
            UserNews.is_read.is_(True),
        )
    )
    read_query = _apply_category_filter(read_query, category)
    if stock_id:
        read_query = read_query.where(News.stock_id == stock_id)

    read_result = await db.execute(read_query)
    read_count = read_result.scalar() or 0

    return max(0, total_count - read_count)


async def batch_transform_kap_to_news(db: AsyncSession, symbol: str) -> int:
    """
    Transform all untransformed KapReports to News for a given symbol.

    Called by KAP ingestion service after sync.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol to transform KapReports for

    Returns:
        Count of newly transformed reports
    """
    # Resolve stock_id from symbol
    stock_result = await db.execute(select(Stock.id).where(Stock.symbol == symbol.upper()))
    stock_id = stock_result.scalar_one_or_none()
    if stock_id is None:
        return 0

    # Get all KapReports for this stock
    result = await db.execute(
        select(KapReport).where(KapReport.stock_id == stock_id)
    )
    kap_reports = result.scalars().all()

    count = 0
    for kap in kap_reports:
        # Check if already transformed (get-or-create logic)
        existing = await db.execute(
            select(News).where(
                News.source_type == "kap",
                News.source_id == kap.id,
            )
        )
        if existing.scalar_one_or_none():
            continue  # Already exists

        news = await transform_kap_to_news(db, kap)
        if news:
            count += 1

    return count


async def backfill_news_from_kap_reports(db: AsyncSession) -> int:
    """
    Backfill News rows from existing KAP reports.

    This is used to bootstrap the news feed for databases that already had
    KAP reports before the KAP -> News hook was introduced.
    """
    stock_symbols_result = await db.execute(
        select(distinct(Stock.symbol))
        .join(KapReport, KapReport.stock_id == Stock.id)
        .where(KapReport.stock_id.is_not(None))
    )
    symbols = [symbol for symbol in stock_symbols_result.scalars().all() if symbol]

    total_created = 0
    for symbol in symbols:
        total_created += await batch_transform_kap_to_news(db, symbol)

    return total_created
