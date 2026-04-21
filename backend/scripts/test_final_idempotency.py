
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import AsyncSessionLocal
from app.models.kap_report import KapReport
from app.services.pipeline.chunking_service import chunk_single_pdf

async def test_clean_idempotency():
    print("\n--- ULTIMATE IDEMPOTENCY TEST START ---")
    async with AsyncSessionLocal() as db:
        # 1. Pick a report (ID 216 was our hero last time)
        report = (await db.get(KapReport, 216))
        
        if not report:
            print("Report 216 not found, picking another one...")
            report = (await db.execute(select(KapReport).where(KapReport.rag_ingest_status == 'INGESTED').limit(1))).scalars().first()
            
        if not report:
            print("No report found at all!")
            return
            
        print(f"Testing with Report ID: {report.id} (Stock ID: {report.stock_id})")
        
        # Reset to ELIGIBLE to simulate a fresh retry/refresh
        print("Resetting report status to ELIGIBLE...")
        report.rag_ingest_status = 'ELIGIBLE'
        report.rag_ingest_reason = None
        await db.commit()
        await db.refresh(report)
        
        # We need to peek inside the parser result
        from app.services.pipeline.document_parser import get_structured_pdf_parser
        parser = get_structured_pdf_parser()
        pdf_full_path = Path("data/pdfs") / report.local_pdf_path
        parsed_doc = parser.parse(pdf_full_path)
        print(f"DEBUG: Parsed Markdown Length: {len(parsed_doc.markdown)}")
        print(f"DEBUG: Elements count: {len(parsed_doc.elements)}")
        if len(parsed_doc.markdown) > 100:
            print(f"DEBUG: Snippet: {parsed_doc.markdown[:100]}...")

        result = await chunk_single_pdf(db, report, Path("data/pdfs"))
        
        print("\n--- VERIFICATION ---")
        print(f"Success: {result.success}")
        print(f"New Chunks Created: {result.chunks_created}")
        print(f"Existing Chunks Skipped: {result.chunks_skipped}")
        
        # Verify final status
        await db.refresh(report)
        print(f"Final DB Status: {report.rag_ingest_status}")
        print(f"Final DB Reason: {report.rag_ingest_reason}")
        print(f"Final DB Count: {report.chunk_count}")
        
        if report.rag_ingest_reason == 'idempotent_refresh':
            print("\nPROVEN: System correctly identified and handled existing content!")
        else:
            print(f"\nFAILED: System reason was '{report.rag_ingest_reason}' instead of 'idempotent_refresh'")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_clean_idempotency())
