"""Mappers from KapFiling provider model to KapReport SQLAlchemy model."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.data.provider_models import KapFiling
from app.services.utils.logging import logger


def normalize_related_stocks(related_stocks: Sequence[str] | str | None) -> list[str] | None:
    """
    Normalize related_stocks string to JSON array for PostgreSQL JSONB storage.

    Args:
        related_stocks: Comma-separated string or list of stock symbols.

    Returns:
        List of normalized symbols (e.g., ["THYAO", "GARAN", "ASELS"]) or None
    """
    if not related_stocks:
        return None

    if isinstance(related_stocks, str):
        raw_stocks = related_stocks.split(',')
    else:
        raw_stocks = [str(stock) for stock in related_stocks]

    stocks = [s.strip().upper() for s in raw_stocks]
    # Boşları at, duplicate'leri temizle
    stocks = [s for s in stocks if s]
    stocks = list(dict.fromkeys(stocks))  # Preserve order, remove duplicates
    return stocks if stocks else None


async def get_stock_id_by_symbol(db: AsyncSession, symbol: str) -> int | None:
    """
    Get stock database ID from symbol.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol (e.g., "THYAO")

    Returns:
        Stock ID if found, None otherwise
    """
    result = await db.execute(
        select(Stock.id).where(Stock.symbol == symbol.upper())
    )
    return result.scalar_one_or_none()


async def map_kap_filing_to_model(
    db: AsyncSession,
    symbol: str,
    filing: KapFiling,
) -> KapReport | None:
    """
    Convert KapFiling to KapReport SQLAlchemy model.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        filing: Provider KapFiling data

    Returns:
        KapReport model instance, or None if stock not found in database
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        logger.warning(f"Stock not found for symbol {symbol}")
        return None

    return KapReport(
        stock_id=stock_id,
        title=filing.title,
        filing_type=filing.filing_type,
        pdf_url=filing.pdf_url,
        source_url=filing.source_url,
        published_at=filing.published_at,
        provider=filing.provider.value,
        sync_status="PENDING",
        chunk_count=0,
        # Enrichment fields
        summary=filing.summary,
        attachment_count=filing.attachment_count,
        is_late=filing.is_late,
        related_stocks=normalize_related_stocks(filing.related_stocks),
    )


async def upsert_kap_filings(
    db: AsyncSession,
    symbol: str,
    filings: Sequence[KapFiling],
) -> int:
    """
    Upsert multiple KAP filings into database.

    Uses PostgreSQL INSERT ... ON CONFLICT for efficient upsert.
    Handles duplicate records gracefully based on (stock_id, source_url) unique constraint.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        filings: Sequence of KapFiling objects to upsert

    Returns:
        Count of inserted/updated records
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        logger.warning(f"Stock not found for symbol {symbol}, skipping {len(filings)} filings")
        return 0

    count = 0
    for filing in filings:
        # Skip filings without source_url (can't deduplicate)
        if filing.source_url is None:
            logger.debug(f"Skipping filing without source_url: {filing.title[:50]}...")
            continue

        # PostgreSQL upsert using ON CONFLICT on unique constraint
        stmt = insert(KapReport).values(
            stock_id=stock_id,
            title=filing.title,
            filing_type=filing.filing_type,
            pdf_url=filing.pdf_url,
            source_url=filing.source_url,
            published_at=filing.published_at,
            provider=filing.provider.value,
            sync_status="PENDING",
            chunk_count=0,
            # Enrichment fields
            summary=filing.summary,
            attachment_count=filing.attachment_count,
            is_late=filing.is_late,
            related_stocks=normalize_related_stocks(filing.related_stocks),
        )

        # On conflict (stock_id, source_url), update metadata
        stmt = stmt.on_conflict_do_update(
            constraint="uq_kap_report_stock_source",
            set_={
                "title": stmt.excluded.title,
                "filing_type": stmt.excluded.filing_type,
                "pdf_url": stmt.excluded.pdf_url,
                "published_at": stmt.excluded.published_at,
                "provider": stmt.excluded.provider,
                # Enrichment fields
                "summary": stmt.excluded.summary,
                "attachment_count": stmt.excluded.attachment_count,
                "is_late": stmt.excluded.is_late,
                "related_stocks": stmt.excluded.related_stocks,
            }
        )

        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info(f"Upserted {count} KAP filings for {symbol}")
    return count


async def get_kap_reports_for_stock(
    db: AsyncSession,
    symbol: str,
    limit: int = 50,
    filing_types: list[str] | None = None,
) -> list[KapReport]:
    """
    Get KAP reports from database for a stock.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        limit: Maximum number of reports to return
        filing_types: Optional filter by filing types

    Returns:
        List of KapReport model instances, ordered by published_at desc
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return []

    query = select(KapReport).where(KapReport.stock_id == stock_id)

    if filing_types:
        query = query.where(KapReport.filing_type.in_(filing_types))

    query = query.order_by(KapReport.published_at.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_kap_reports_for_stock(
    db: AsyncSession,
    symbol: str,
) -> int:
    """
    Delete all KAP reports for a stock.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol

    Returns:
        Count of deleted records
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return 0

    result = await db.execute(
        select(KapReport).where(KapReport.stock_id == stock_id)
    )
    reports = result.scalars().all()

    for report in reports:
        await db.delete(report)

    await db.commit()
    return len(reports)
