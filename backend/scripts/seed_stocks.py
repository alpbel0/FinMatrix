"""
Seed script to populate stocks table with BIST stocks.

Run with: cd backend && PYTHONPATH=$(pwd) python scripts/seed_stocks.py
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine
from app.models import Stock

# 20 BIST stocks with sector information
BIST_STOCKS = [
    {"symbol": "THYAO", "yfinance_symbol": "THYAO.IS", "company_name": "Türk Hava Yolları", "sector": "Havacılık"},
    {"symbol": "ASELS", "yfinance_symbol": "ASELS.IS", "company_name": "Aselsan", "sector": "Savunma"},
    {"symbol": "GARAN", "yfinance_symbol": "GARAN.IS", "company_name": "Garanti BBVA", "sector": "Bankacılık"},
    {"symbol": "BIMAS", "yfinance_symbol": "BIMAS.IS", "company_name": "BİM Birleşik Mağazalar", "sector": "Perakende"},
    {"symbol": "SISE", "yfinance_symbol": "SISE.IS", "company_name": "Şişe Cam", "sector": "Sanayi"},
    {"symbol": "EREGL", "yfinance_symbol": "EREGL.IS", "company_name": "Ereğli Demir Çelik", "sector": "Metal"},
    {"symbol": "KCHOL", "yfinance_symbol": "KCHOL.IS", "company_name": "Koç Holding", "sector": "Holding"},
    {"symbol": "AKBNK", "yfinance_symbol": "AKBNK.IS", "company_name": "Akbank", "sector": "Bankacılık"},
    {"symbol": "TUPRS", "yfinance_symbol": "TUPRS.IS", "company_name": "Tüpraş", "sector": "Enerji"},
    {"symbol": "SAHOL", "yfinance_symbol": "SAHOL.IS", "company_name": "Sabancı Holding", "sector": "Holding"},
    {"symbol": "TOASO", "yfinance_symbol": "TOASO.IS", "company_name": "Tofaş", "sector": "Otomotiv"},
    {"symbol": "FROTO", "yfinance_symbol": "FROTO.IS", "company_name": "Ford Otosan", "sector": "Otomotiv"},
    {"symbol": "TCELL", "yfinance_symbol": "TCELL.IS", "company_name": "Turkcell", "sector": "Telekomünikasyon"},
    {"symbol": "HEKTS", "yfinance_symbol": "HEKTS.IS", "company_name": "Hektaş", "sector": "Kimya"},
    {"symbol": "PGSUS", "yfinance_symbol": "PGSUS.IS", "company_name": "Pegasus", "sector": "Havacılık"},
    {"symbol": "KOZAA", "yfinance_symbol": "KOZAA.IS", "company_name": "Koza Altın", "sector": "Madencilik"},
    {"symbol": "SASA", "yfinance_symbol": "SASA.IS", "company_name": "Sasa Polyester", "sector": "Kimya"},
    {"symbol": "ENKAI", "yfinance_symbol": "ENKAI.IS", "company_name": "Enka İnşaat", "sector": "İnşaat"},
    {"symbol": "TAVHL", "yfinance_symbol": "TAVHL.IS", "company_name": "TAV Havalimanları", "sector": "Havacılık"},
    {"symbol": "PETKM", "yfinance_symbol": "PETKM.IS", "company_name": "Petkim", "sector": "Petrokimya"},
]


async def seed_stocks(session: AsyncSession) -> int:
    """
    Seed stocks table with BIST stocks.

    Returns the number of stocks inserted.
    """
    inserted_count = 0

    for stock_data in BIST_STOCKS:
        # Check if stock already exists
        result = await session.execute(
            select(Stock).where(Stock.symbol == stock_data["symbol"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  [SKIP] {stock_data['symbol']} already exists")
            continue

        # Create new stock
        stock = Stock(**stock_data)
        session.add(stock)
        inserted_count += 1
        print(f"  [ADD] {stock_data['symbol']} - {stock_data['company_name']}")

    await session.commit()
    return inserted_count


async def main() -> None:
    """Main entry point for seed script."""
    print("=" * 50)
    print("Seeding BIST stocks...")
    print("=" * 50)

    async with AsyncSessionLocal() as session:
        try:
            inserted = await seed_stocks(session)
            print("=" * 50)
            print(f"Done! Inserted {inserted} stocks.")
            print("=" * 50)
        except Exception as e:
            print(f"Error seeding stocks: {e}")
            await session.rollback()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())