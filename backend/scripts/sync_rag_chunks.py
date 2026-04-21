
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import AsyncSessionLocal
from app.services.pipeline.chunking_service import batch_chunk_completed_pdfs

async def main():
    print("Starting RAG 2.0 Chunking Sync...")
    print("Processing ELIGIBLE reports using Docling parser...")
    
    async with AsyncSessionLocal() as db:
        result = await batch_chunk_completed_pdfs(db, limit=50)
        
        print("\nChunking Finished!")
        print(f"Total Processed: {result.total_processed}")
        print(f"Successful: {result.successful}")
        print(f"Failed: {result.failed}")
        print(f"Status: {result.status.upper()}")
        
        if result.failed > 0:
            print("\nErrors encountered:")
            for r in result.results:
                if not r.success:
                    print(f"  - Report {r.kap_report_id} ({r.symbol}): {r.error_message}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
