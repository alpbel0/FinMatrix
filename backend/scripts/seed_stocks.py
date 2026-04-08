"""Seed BIST stocks and backfill price history from provider."""

import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.stock import Stock
from app.services.data.mappers.stock_price_mapper import upsert_price_bars
from app.services.data.provider_registry import get_provider_for_prices
from app.services.utils.logging import logger


# BIST stocks for MVP - 10 major stocks across sectors
BIST_STOCKS = [
    {"symbol": "THYAO", "company_name": "Turk Hava Yollari AO", "sector": "Transportation"},
    {"symbol": "GARAN", "company_name": "Garanti Bankasi TAS", "sector": "Finance"},
    {"symbol": "SAHOL", "company_name": "Sabanci Holding", "sector": "Conglomerates"},
    {"symbol": "AKBNK", "company_name": "Akbank TAS", "sector": "Finance"},
    {"symbol": "ASELS", "company_name": "Aselsan Elektronik", "sector": "Defense"},
    {"symbol": "EREGL", "company_name": "Eregli Demir ve Celik Fabrikalari TAS", "sector": "Steel"},
    {"symbol": "TKFEN", "company_name": "Tekfen Holding", "sector": "Construction"},
    {"symbol": "KOZAA", "company_name": "Koza Altin Isletmeleri AS", "sector": "Mining"},
    {"symbol": "ISCTR", "company_name": "Turkiye Is Bankasi TAS", "sector": "Finance"},
    {"symbol": "YKBNK", "company_name": "Yapi ve Kredi Bankasi AS", "sector": "Finance"},
]


async def seed_stocks(db: AsyncSession) -> int:
    """
    Upsert BIST stocks into database.

    Uses INSERT ... ON CONFLICT DO UPDATE for idempotent seeding.

    Returns:
        Count of stocks inserted/updated
    """
    logger.info(f"Seeding {len(BIST_STOCKS)} stocks...")

    count = 0
    for stock_data in BIST_STOCKS:
        stmt = insert(Stock).values(
            symbol=stock_data["symbol"],
            company_name=stock_data["company_name"],
            sector=stock_data["sector"],
            exchange="BIST",
            is_active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "company_name": stmt.excluded.company_name,
                "sector": stmt.excluded.sector,
                "is_active": stmt.excluded.is_active,
            }
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info(f"Seeded {count} stocks successfully")
    return count


async def backfill_prices(db: AsyncSession, period: str = "1y") -> dict[str, int]:
    """
    Backfill price history for all seeded stocks.

    Uses BorsapyProvider to fetch historical prices and upserts to DB.

    Args:
        db: Database session
        period: Time period to fetch ("1mo", "1y", "max")

    Returns:
        Dict mapping symbol to count of price bars inserted
    """
    logger.info(f"Backfilling prices for period '{period}'...")

    # Get seeded stocks
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = list(result.scalars().all())

    if not stocks:
        logger.warning("No stocks found in database. Run seed_stocks() first.")
        return {}

    symbols = [s.symbol for s in stocks]
    logger.info(f"Fetching prices for {len(symbols)} stocks: {symbols}")

    # Get provider and fetch prices
    provider = get_provider_for_prices()

    results = {}
    for symbol in symbols:
        try:
            logger.info(f"Fetching price history for {symbol}...")
            price_bars = provider.get_price_history(symbol, period=period)

            if not price_bars:
                logger.warning(f"No price data returned for {symbol}")
                results[symbol] = 0
                continue

            logger.info(f"Upserting {len(price_bars)} price bars for {symbol}...")
            count = await upsert_price_bars(db, symbol, list(price_bars))
            results[symbol] = count
            logger.info(f"Inserted {count} price bars for {symbol}")

        except Exception as exc:
            logger.error(f"Failed to backfill prices for {symbol}: {exc}")
            results[symbol] = 0

    return results


async def main() -> None:
    """Run full seed pipeline: stocks + prices."""
    logger.info("Starting seed pipeline...")

    async with AsyncSessionLocal() as db:
        # Step 1: Seed stocks
        stock_count = await seed_stocks(db)

        # Step 2: Backfill prices
        price_counts = await backfill_prices(db, period="1y")

        # Summary
        total_prices = sum(price_counts.values())
        logger.info(f"Seed complete: {stock_count} stocks, {total_prices} price bars")

        for symbol, count in price_counts.items():
            logger.info(f"  {symbol}: {count} price bars")


if __name__ == "__main__":
    asyncio.run(main())