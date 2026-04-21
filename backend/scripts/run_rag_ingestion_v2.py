
import asyncio
import sys
import logging
from pathlib import Path
from sqlalchemy import select, and_

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import AsyncSessionLocal
from app.models.kap_report import KapReport
from app.services.pipeline.chunking_service import chunk_single_pdf, ChunkingStatus

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("RAG-Ingestion-v2")

async def run_batch_ingestion():
    logger.info("--- RAG 2.0 BATCH INGESTION START ---")
    
    async with AsyncSessionLocal() as db:
        # 1. Find all reports that are ELIGIBLE but not yet COMPLETED
        query = select(KapReport).where(
            and_(
                KapReport.rag_ingest_status == 'ELIGIBLE',
                KapReport.chunking_status != ChunkingStatus.COMPLETED.value
            )
        )
        result = await db.execute(query)
        reports = result.scalars().all()
        
        total_count = len(reports)
        if total_count == 0:
            logger.info("No eligible reports pending for RAG ingestion.")
            return

        logger.info(f"Found {total_count} reports to process. Buckle up!")
        
        pdf_dir = Path("data/pdfs")
        success_count = 0
        fail_count = 0
        
        # 2. Iterate and process
        for idx, report in enumerate(reports, 1):
            logger.info(f"[{idx}/{total_count}] Processing ID {report.id} ({report.local_pdf_path})...")
            
            try:
                # Use our core service function (Docling + RAG 2.0 Dedupe logic)
                res = await chunk_single_pdf(db, report, pdf_dir)
                
                if res.success:
                    success_count += 1
                    logger.info(f"   SUCCESS: {res.chunks_created} new, {res.chunks_skipped} duplicates/idempotent.")
                else:
                    fail_count += 1
                    logger.warning(f"   FAILED: {res.error_message}")
            except Exception as e:
                fail_count += 1
                logger.error(f"   CRASH while processing {report.id}: {str(e)}")
            
            # Periodically commit just in case? (chunk_single_pdf already commits, but let's be sure)
            if idx % 5 == 0:
                await db.commit()
                logger.info(f"Progress check: {success_count} succeeded, {fail_count} failed.")

    logger.info("--- BATCH INGESTION FINISHED ---")
    logger.info(f"Grand Total: {total_count}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed/Skipped: {fail_count}")
    logger.info("Don't forget to run sync_rag_memory.py afterwards to push updates to ChromaDB!")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_batch_ingestion())
