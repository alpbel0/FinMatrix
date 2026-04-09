"""Job policy module for scheduler universe selection.

This module provides functions to determine which stocks should be included
in various scheduler job universes:

- All active stocks: For price sync
- BIST 100: For hourly KAP sync and financial sync
- Watchlist: For daily KAP sync
- Slow sync: Active - watchlist - BIST100 (for 3-day KAP sync)
"""

from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.models.watchlist import Watchlist
from app.services.data.providers.bist_index_provider import get_bist100_symbols


async def get_all_active_symbols(db: AsyncSession) -> list[str]:
    """Get all active stock symbols from database.

    Args:
        db: AsyncSession instance

    Returns:
        List of active stock symbols (e.g., ["THYAO", "GARAN", ...])
    """
    result = await db.execute(
        select(Stock.symbol).where(Stock.is_active == True).order_by(Stock.symbol)
    )
    return [row[0] for row in result.all()]


async def get_bist100_symbols_from_provider() -> list[str]:
    """Get BIST 100 symbols from borsapy provider.

    This wraps the provider adapter for consistency with other job policy functions.

    Returns:
        List of BIST 100 symbols. Empty list if provider fails.
    """
    return get_bist100_symbols()


async def get_watchlist_symbols(db: AsyncSession) -> list[str]:
    """Get symbols from all users' watchlists (union).

    This returns the union of all watchlisted stocks across all users,
    used for the daily KAP sync job.

    Args:
        db: AsyncSession instance

    Returns:
        List of unique symbols that appear in any user's watchlist.
    """
    # Join watchlist with stocks to get symbols
    result = await db.execute(
        select(distinct(Stock.symbol))
        .select_from(Watchlist)
        .join(Stock, Watchlist.stock_id == Stock.id)
        .where(Stock.is_active == True)
        .order_by(Stock.symbol)
    )
    return [row[0] for row in result.all()]


async def get_slow_sync_symbols(db: AsyncSession) -> list[str]:
    """Get symbols for KAP slow sync job.

    Universe: Active stocks - Watchlist - BIST 100

    This excludes:
    - BIST 100: Already covered by hourly KAP sync
    - Watchlist: Already covered by daily KAP sync

    Args:
        db: AsyncSession instance

    Returns:
        List of symbols for slow sync (3-day interval).
    """
    # Get all active symbols
    active = await get_all_active_symbols(db)

    # Get watchlist symbols
    watchlist = await get_watchlist_symbols(db)

    # Get BIST 100 symbols
    bist100 = await get_bist100_symbols_from_provider()

    # Calculate exclusion set
    excluded = set(watchlist) | set(bist100)

    # Return active symbols not in excluded set
    return [symbol for symbol in active if symbol not in excluded]


async def get_symbols_by_universe(
    db: AsyncSession, universe: str
) -> list[str]:
    """Get symbols for a named universe.

    Args:
        db: AsyncSession instance
        universe: Universe name - "all", "bist100", "watchlist", or "slow"

    Returns:
        List of symbols for the specified universe.

    Raises:
        ValueError: If universe name is not recognized.
    """
    universe = universe.lower()

    if universe == "all":
        return await get_all_active_symbols(db)
    elif universe == "bist100":
        return await get_bist100_symbols_from_provider()
    elif universe == "watchlist":
        return await get_watchlist_symbols(db)
    elif universe == "slow":
        return await get_slow_sync_symbols(db)
    else:
        raise ValueError(
            f"Unknown universe: {universe}. "
            f"Valid options: all, bist100, watchlist, slow"
        )