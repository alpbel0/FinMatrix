"""Mappers from provider models to SQLAlchemy models."""

from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.services.data.provider_models import PriceBar, DataSource


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


async def map_price_bar_to_model(
    db: AsyncSession,
    symbol: str,
    price_bar: PriceBar,
) -> StockPrice | None:
    """
    Convert PriceBar to StockPrice SQLAlchemy model.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        price_bar: Provider price bar data

    Returns:
        StockPrice model instance, or None if stock not found in database
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return None

    return StockPrice(
        stock_id=stock_id,
        date=price_bar.date,
        open=price_bar.open,
        high=price_bar.high,
        low=price_bar.low,
        close=price_bar.close,
        volume=price_bar.volume,
        adjusted_close=price_bar.adjusted_close,
        source=price_bar.source.value,
    )


async def upsert_price_bars(
    db: AsyncSession,
    symbol: str,
    bars: list[PriceBar],
) -> int:
    """
    Upsert multiple price bars into database.

    Uses PostgreSQL INSERT ... ON CONFLICT for efficient upsert.
    Handles duplicate records gracefully.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        bars: List of PriceBar objects to upsert

    Returns:
        Count of inserted/updated records
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return 0

    count = 0
    for bar in bars:
        # PostgreSQL upsert using ON CONFLICT
        stmt = insert(StockPrice).values(
            stock_id=stock_id,
            date=bar.date,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            adjusted_close=bar.adjusted_close,
            source=bar.source.value,
        )

        # On conflict, update all OHLCV fields
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "adjusted_close": stmt.excluded.adjusted_close,
                "source": stmt.excluded.source,
            }
        )

        await db.execute(stmt)
        count += 1

    await db.commit()
    return count


async def get_price_bars_for_stock(
    db: AsyncSession,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[StockPrice]:
    """
    Get price history from database for a stock.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of StockPrice model instances
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return []

    query = select(StockPrice).where(StockPrice.stock_id == stock_id)

    if start_date:
        query = query.where(StockPrice.date >= start_date)
    if end_date:
        query = query.where(StockPrice.date <= end_date)

    query = query.order_by(StockPrice.date.asc())

    result = await db.execute(query)
    return list(result.scalars().all())