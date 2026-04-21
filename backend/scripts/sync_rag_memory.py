
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import AsyncSessionLocal
from app.services.pipeline.embedding_service import batch_embed_pending_chunks

async def main():
    print("Starting RAG 2.0 Embedding Sync...")
    print("Connecting to database and processing pending content chunks...")
    
    async with AsyncSessionLocal() as db:
        result = await batch_embed_pending_chunks(db, limit=500)
        
        print("\nSync Finished!")
        print(f"Total Processed: {result.total_processed}")
        print(f"Successful: {result.successful}")
        print(f"Failed: {result.failed}")
        print(f"Status: {result.status.upper()}")
        
        if result.failed > 0:
            print("\nErrors encountered:")
            for r in result.results:
                if not r.success:
                    print(f"  - Chunk {r.chunk_id}: {r.error_message}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
