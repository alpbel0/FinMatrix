
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

async def test_pdf_overlap():
    print("\n--- REAL PDF CONTENT OVERLAP TEST ---")
    async with AsyncSessionLocal() as db:
        # 1. Get two reports for the same stock (Stock 1)
        reports = (await db.execute(
            select(KapReport).where(KapReport.stock_id == 1).limit(2)
        )).scalars().all()
        
        if len(reports) < 2:
            print("Required data not found!")
            return
            
        r1, r2 = reports[0], reports[1]
        print(f"Testing Overlap between PDF 1 ({r1.id}) and PDF 2 ({r2.id})")
        
        # Reset both to ELIGIBLE to ensure we process them fresh
        for r in reports:
            r.rag_ingest_status = 'ELIGIBLE'
            r.rag_ingest_reason = None
            r.chunk_count = 0
            
        await db.commit()
        
        # 2. PROCESS PDF 1
        print(f"\nProcessing PDF 1: {r1.local_pdf_path}...")
        res1 = await chunk_single_pdf(db, r1, Path("data/pdfs"))
        print(f"PDF 1 -> Created: {res1.chunks_created}")
        
        # 3. PROCESS PDF 2 with the SAME PDF as PDF 1 (FORCED OVERLAP TEST)
        print(f"\nProcessing PDF 2 (FORCED OVERLAP with PDF 1's file)...")
        # Temporarily use PDF 1's path for PDF 2's ingestion
        orig_path = r2.local_pdf_path
        r2.local_pdf_path = r1.local_pdf_path  # Force it to read the same file
        
        # Diagnostics: Let's see the first element hash
        from app.services.pipeline.content_ingestion_service import build_stock_scoped_content_hash, normalize_content_text
        from app.services.pipeline.document_parser import get_structured_pdf_parser
        doc = get_structured_pdf_parser().parse(Path("data/pdfs") / r1.local_pdf_path)
        first_text = doc.elements[0].text
        h = build_stock_scoped_content_hash(r1.stock_id, first_text)
        print(f"DEBUG: First element text snippet: {first_text[:50]}...")
        print(f"DEBUG: Calculated Hash: {h}")
        
        res2 = await chunk_single_pdf(db, r2, Path("data/pdfs"))
        
        # Restore path
        r2.local_pdf_path = orig_path
        await db.commit()
        
        print("\n--- FINAL OVERLAP RESULT ---")
        print(f"PDF 2 (Same File) -> New Chunks Created: {res2.chunks_created}")
        print(f"PDF 2 (Same File) -> Existing Chunks Linked: {res2.chunks_linked}")
        print(f"PDF 2 (Same File) -> Chunks Already Link (Skipped): {res2.chunks_skipped}")
        
        if res2.chunks_linked > 0 and res2.chunks_created == 0:
            print(f"\nSUCCESS: System successfully LINKED to {res2.chunks_linked} existing chunks instead of creating duplicates!")
        else:
            print("\nFAILED: Deduplication across reports failed or was already idempotent.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_pdf_overlap())
