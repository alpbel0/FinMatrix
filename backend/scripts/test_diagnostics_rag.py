
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
from app.services.pipeline.content_ingestion_service import assemble_content_elements, prepend_summary_element
from app.services.pipeline.document_parser import get_structured_pdf_parser
from app.config import get_settings

async def test_ultimate_diagnostics():
    print("\n--- ULTIMATE RAG 2.0 DIAGNOSTICS ---")
    async with AsyncSessionLocal() as db:
        report = (await db.get(KapReport, 216))
        if not report:
            print("Report 216 not found!")
            return
            
        print(f"Report: {report.id}, Stock: {report.stock_id}, Status: {report.rag_ingest_status}")
        
        # Reset but keep INGESTED for idempotency test
        report.rag_ingest_status = 'ELIGIBLE' 
        await db.commit()
        
        # STEP 1: Parse
        parser = get_structured_pdf_parser()
        pdf_path = Path("data/pdfs") / report.local_pdf_path
        print(f"Parsing {pdf_path}...")
        parsed_doc = parser.parse(pdf_path)
        print(f"Raw Elements: {len(parsed_doc.elements)}")
        
        # STEP 2: Enriched elements
        enriched = prepend_summary_element(parsed_doc, report.summary)
        print(f"Enriched Elements: {len(enriched.elements)}")
        
        # STEP 3: Assemble
        settings = get_settings()
        print(f"Assembling with target_tokens={settings.chunk_target_tokens}...")
        chunks = assemble_content_elements(enriched, settings.chunk_target_tokens)
        print(f"Assembled Chunks: {len(chunks)}")
        
        if len(chunks) > 0:
            print(f"First Chunk Snippet: {chunks[0].text[:100]}...")
        
        # STEP 4: Final Pipeline Run
        print("\nRunning full chunk_single_pdf pipeline...")
        result = await chunk_single_pdf(db, report, Path("data/pdfs"))
        
        print("\n--- FINAL RESULT ---")
        print(f"Success: {result.success}")
        print(f"New: {result.chunks_created}, Skipped: {result.chunks_skipped}")
        
        await db.refresh(report)
        print(f"DB Status: {report.rag_ingest_status}, Reason: {report.rag_ingest_reason}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_ultimate_diagnostics())
