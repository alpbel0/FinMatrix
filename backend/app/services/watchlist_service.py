"""Watchlist service for user watchlist operations."""

from datetime import date

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.watchlist import Watchlist
from app.models.stock import Stock
from app.models.stock_price import StockPrice


async def get_user_watchlist(db: AsyncSession, user_id: int) -> list[Watchlist]:
    """
    Get all watchlist items for a user with stock info loaded.

    Args:
        db: AsyncSession instance
        user_id: User ID

    Returns:
        List of Watchlist model instances with stock relationship loaded
    """
    query = (
        select(Watchlist)
        .options(joinedload(Watchlist.stock))
        .where(Watchlist.user_id == user_id)
        .order_by(Watchlist.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def get_latest_price_for_stock(db: AsyncSession, stock_id: int) -> StockPrice | None:
    """
    Get the latest price record for a stock.

    Args:
        db: AsyncSession instance
        stock_id: Stock ID

    Returns:
        Latest StockPrice or None
    """
    query = (
        select(StockPrice)
        .where(StockPrice.stock_id == stock_id)
        .order_by(desc(StockPrice.date))
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_previous_price_for_stock(
    db: AsyncSession, stock_id: int, current_date: date
) -> StockPrice | None:
    """
    Get the previous trading day price for change calculation.

    Args:
        db: AsyncSession instance
        stock_id: Stock ID
        current_date: Current price date

    Returns:
        Previous StockPrice or None
    """
    query = (
        select(StockPrice)
        .where(StockPrice.stock_id == stock_id)
        .where(StockPrice.date < current_date)
        .order_by(desc(StockPrice.date))
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def add_to_watchlist(
    db: AsyncSession, user_id: int, stock_id: int, notifications_enabled: bool = True
) -> Watchlist:
    """
    Add a stock to user's watchlist.

    Args:
        db: AsyncSession instance
        user_id: User ID
        stock_id: Stock ID
        notifications_enabled: Whether to enable notifications

    Returns:
        Created Watchlist instance

    Raises:
        IntegrityError: If stock already in watchlist (unique constraint)
    """
    watchlist_item = Watchlist(
        user_id=user_id,
        stock_id=stock_id,
        notifications_enabled=notifications_enabled,
    )
    db.add(watchlist_item)
    await db.commit()
    await db.refresh(watchlist_item)
    return watchlist_item


async def remove_from_watchlist(db: AsyncSession, watchlist_id: int, user_id: int) -> bool:
    """
    Remove a stock from user's watchlist.

    Args:
        db: AsyncSession instance
        watchlist_id: Watchlist item ID
        user_id: User ID (for ownership verification)

    Returns:
        True if removed, False if not found/not owned
    """
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.user_id == user_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        return False
    await db.delete(item)
    await db.commit()
    return True


async def toggle_notifications(
    db: AsyncSession, watchlist_id: int, user_id: int, enabled: bool
) -> Watchlist | None:
    """
    Toggle notifications for a watchlist item.

    Args:
        db: AsyncSession instance
        watchlist_id: Watchlist item ID
        user_id: User ID (for ownership verification)
        enabled: New notifications_enabled value

    Returns:
        Updated Watchlist instance or None if not found/not owned
    """
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.user_id == user_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        return None
    item.notifications_enabled = enabled
    await db.commit()
    await db.refresh(item)
    return item