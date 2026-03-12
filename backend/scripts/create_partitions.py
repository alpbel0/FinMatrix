#!/usr/bin/env python3
"""
Script to create monthly partitions for stock_prices table.

Creates partitions for:
- Past 2 years (historical data backfill)
- Future 6 months (upcoming data collection)

Usage:
    python scripts/create_partitions.py [--dry-run]

Partitions are named: stock_prices_YYYY_MM
Example: stock_prices_2024_01, stock_prices_2024_02
"""

import argparse
import asyncio
import calendar
from datetime import date, datetime
from typing import List, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """
    Add delta months to a (year, month) pair using calendar arithmetic.

    Args:
        year: Base year
        month: Base month (1–12)
        delta: Number of months to add (can be negative)

    Returns:
        (new_year, new_month) tuple
    """
    month += delta
    # Normalize month into 1–12 range
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return year, month


def get_partition_ranges() -> List[Tuple[str, str, str]]:
    """
    Generate partition ranges for past 2 years and future 6 months.

    Uses calendar.monthrange to correctly determine the last day of each
    month, avoiding manual modulo arithmetic for month/year rollovers.

    Returns:
        List of tuples: (partition_name, start_date, end_date)
    """
    now = datetime.now()
    base_year, base_month = now.year, now.month

    # Offsets: -60 … 0 (past 5 years) + 1 … 6 (future 6 months)
    # Extended past to cover old test dates (e.g., 2024-01-01)
    offsets = list(range(-60, 1)) + list(range(1, 7))

    partitions = []
    seen = set()

    for delta in offsets:
        year, month = _add_months(base_year, base_month, delta)

        partition_name = f"stock_prices_{year}_{month:02d}"
        if partition_name in seen:
            continue
        seen.add(partition_name)

        start_date = date(year, month, 1).isoformat()

        # First day of the next month — calendar.monthrange gives days in month
        next_year, next_month = _add_months(year, month, 1)
        end_date = date(next_year, next_month, 1).isoformat()

        partitions.append((partition_name, start_date, end_date))

    partitions.sort(key=lambda x: x[1])
    return partitions


async def create_partitions(dry_run: bool = False) -> None:
    """
    Create monthly partitions for stock_prices table.

    Args:
        dry_run: If True, only print what would be done without executing.
    """
    engine = create_async_engine(settings.effective_database_url)

    partitions = get_partition_ranges()

    print(f"Creating {len(partitions)} partitions for stock_prices table...")
    print("-" * 60)

    async with AsyncSession(engine) as session:
        for partition_name, start_date, end_date in partitions:
            sql = text(f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF stock_prices
                FOR VALUES FROM ('{start_date}') TO ('{end_date}');
            """)

            if dry_run:
                print(f"[DRY RUN] Would create: {partition_name}")
                print(f"           Range: {start_date} to {end_date}")
            else:
                try:
                    await session.execute(sql)
                    print(f"✓ Created partition: {partition_name} ({start_date} to {end_date})")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"○ Partition already exists: {partition_name}")
                    else:
                        print(f"✗ Error creating {partition_name}: {e}")

        if not dry_run:
            await session.commit()

    await engine.dispose()
    print("-" * 60)
    print("Done!")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create monthly partitions for stock_prices table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without executing",
    )
    args = parser.parse_args()

    asyncio.run(create_partitions(dry_run=args.dry_run))


if __name__ == "__main__":
    main()