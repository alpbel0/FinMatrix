"""Backfill KapReport PDF download state from already-downloaded local PDFs."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.data.pdf_download_service import backfill_downloaded_pdfs_from_storage


async def main() -> None:
    settings = get_settings()
    storage_base = Path(settings.pdf_storage_path)

    async with AsyncSessionLocal() as db:
        result = await backfill_downloaded_pdfs_from_storage(db, storage_base=storage_base)

    print("PDF backfill completed")
    print(f"storage_base={storage_base}")
    print(f"total_checked={result.total_checked}")
    print(f"matched={result.matched}")
    print(f"updated={result.updated}")
    print(f"missing={result.missing}")
    print(f"skipped_symbol_mismatch={result.skipped_symbol_mismatch}")


if __name__ == "__main__":
    asyncio.run(main())
