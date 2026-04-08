"""Seed BIST stocks from pykap and optionally backfill price history."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

pykap_path = backend_path.parent / "search" / "pykap"
if pykap_path.exists():
    sys.path.insert(0, str(pykap_path))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.stock import Stock
from app.services.data.mappers.stock_price_mapper import upsert_price_bars
from app.services.data.provider_registry import get_provider_for_prices
from app.services.utils.logging import logger
from pykap.get_bist_companies import get_bist_companies


def fetch_bist_companies() -> list[dict]:
    """Fetch the live BIST company list from KAP via pykap."""
    logger.info("Fetching BIST company list from pykap...")
    companies = get_bist_companies(online=True, output_format="dict")
    logger.info(f"Fetched {len(companies)} BIST companies from KAP")
    return companies


async def seed_stocks(db: AsyncSession) -> int:
    """
    Upsert BIST stocks into database.

    Uses INSERT ... ON CONFLICT DO UPDATE for idempotent seeding.

    Returns:
        Count of stocks inserted/updated
    """
    companies = fetch_bist_companies()
    logger.info(f"Seeding {len(companies)} stocks...")

    count = 0
    for company in companies:
        symbol = (company.get("ticker") or "").strip().upper()
        if not symbol:
            continue

        stmt = insert(Stock).values(
            symbol=symbol,
            company_name=company.get("name"),
            sector=None,
            exchange="BIST",
            is_active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "company_name": stmt.excluded.company_name,
                "exchange": stmt.excluded.exchange,
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


async def main(with_prices: bool = False, period: str = "1y") -> None:
    """Run stock seed pipeline and optionally backfill prices."""
    logger.info("Starting seed pipeline...")

    async with AsyncSessionLocal() as db:
        # Step 1: Seed stocks
        stock_count = await seed_stocks(db)

        if with_prices:
            price_counts = await backfill_prices(db, period=period)
            total_prices = sum(price_counts.values())
            logger.info(f"Seed complete: {stock_count} stocks, {total_prices} price bars")

            for symbol, count in price_counts.items():
                logger.info(f"  {symbol}: {count} price bars")
        else:
            logger.info(f"Seed complete: {stock_count} stocks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed BIST stocks into the database.")
    parser.add_argument(
        "--with-prices",
        action="store_true",
        help="Also backfill price history for all active stocks after seeding.",
    )
    parser.add_argument(
        "--period",
        default="1y",
        help="Price backfill period to use with --with-prices (default: 1y).",
    )
    args = parser.parse_args()
    asyncio.run(main(with_prices=args.with_prices, period=args.period))
