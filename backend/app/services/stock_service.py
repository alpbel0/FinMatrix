"""Stock service for querying stock data from database."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.services.data.mappers.stock_price_mapper import get_price_bars_for_stock
from app.services.snapshot_service import (
    get_historical_stock_snapshots_payload,
    get_latest_stock_snapshot_payload,
)


async def get_all_stocks(db: AsyncSession, search: str | None = None) -> list[Stock]:
    """
    Get all active stocks with optional symbol search filter.

    Args:
        db: AsyncSession instance
        search: Optional substring to filter symbols (case-insensitive)

    Returns:
        List of Stock model instances
    """
    query = select(Stock).where(Stock.is_active == True)

    if search:
        # Case-insensitive symbol search using ILIKE
        query = query.where(Stock.symbol.ilike(f"%{search.upper()}%"))

    query = query.order_by(Stock.symbol.asc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_stock_by_symbol(db: AsyncSession, symbol: str) -> Stock | None:
    """
    Get a single stock by its symbol.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol (e.g., "THYAO")

    Returns:
        Stock model instance if found, None otherwise
    """
    result = await db.execute(
        select(Stock).where(Stock.symbol == symbol.upper())
    )
    return result.scalar_one_or_none()


async def get_price_history(
    db: AsyncSession,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[StockPrice]:
    """
    Get price history for a stock from database.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of StockPrice model instances ordered by date ascending
    """
    return await get_price_bars_for_stock(db, symbol, start_date, end_date)


async def get_latest_stock_snapshot(db: AsyncSession, symbol: str) -> dict:
    """Get latest stored snapshot payload for a stock."""
    return await get_latest_stock_snapshot_payload(db, symbol)


async def get_stock_snapshot_history(
    db: AsyncSession,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Get historical stored snapshots for a stock."""
    return await get_historical_stock_snapshots_payload(db, symbol, start_date, end_date)
