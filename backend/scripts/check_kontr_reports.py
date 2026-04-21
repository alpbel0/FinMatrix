
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import AsyncSessionLocal
from app.models.kap_report import KapReport

async def check():
    async with AsyncSessionLocal() as db:
        reports = (await db.execute(select(KapReport).where(KapReport.local_pdf_path.like('KONTR/2025/%')))).scalars().all()
        for r in reports:
            print(f"ID: {r.id} | Path: {r.local_pdf_path} | Type: {r.filing_type}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check())
