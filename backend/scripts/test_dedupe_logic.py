
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select, func

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import AsyncSessionLocal
from app.models.document_content import DocumentContent
from app.models.chunk_report_link import ChunkReportLink
from app.models.kap_report import KapReport
from app.services.pipeline.content_ingestion_service import persist_parsed_document
from app.services.pipeline.document_parser import ParsedDocument, ParsedElement

async def test_deduplication():
    print("\n--- DEDUPLICATION (CROSS-REPORT) TEST ---")
    async with AsyncSessionLocal() as db:
        # 1. Get two reports for the SAME stock explicitly
        stock_with_multiple = (await db.execute(
            select(KapReport.stock_id)
            .group_by(KapReport.stock_id)
            .having(func.count(KapReport.id) > 1)
            .limit(1)
        )).scalar()
        
        if not stock_with_multiple:
            print("No stock with multiple reports found!")
            return
            
        reports = (await db.execute(
            select(KapReport).where(KapReport.stock_id == stock_with_multiple).limit(2)
        )).scalars().all()
        
        r1, r2 = reports[0], reports[1]
        print(f"Report 1: {r1.id}, Report 2: {r2.id} (CONFIRMED Same Stock: {r1.stock_id})")
        
        # Clear summaries to avoid interference
        r1.summary = None
        r2.summary = None
        await db.commit()
        
        # 2. Create a dummy ParsedDocument
        print("Creating a unique piece of content...")
        import uuid
        unique_text = f"DEDUPE_TEST_{uuid.uuid4()}"
        dummy_doc = ParsedDocument(
            parser_version="test",
            markdown=unique_text,
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text=unique_text,
                    markdown=unique_text,
                    page_start=1,
                    page_end=1,
                    section_path="Test",
                    token_estimate=10,
                    is_atomic=False,
                    content_origin="test"
                )
            ]
        )
        
        # 3. Ingest for Report 1
        print(f"Ingesting into Report {r1.id}...")
        res1 = await persist_parsed_document(db, r1, r1.stock_id, dummy_doc)
        await db.commit()
        print(f"Report 1 -> New Contents Created: {res1.created_count}")
        
        # 4. Ingest SAME content for Report 2
        print(f"Ingesting SAME content into Report {r2.id}...")
        res2 = await persist_parsed_document(db, r2, r2.stock_id, dummy_doc)
        await db.commit()
        print(f"Report 2 -> New Contents Created: {res2.created_count}")
        print(f"Report 2 -> Linked Existing: {res2.linked_count}")
        
        # 5. FINAL PROOF: Count entries in DocumentContent with this text
        content_count = (await db.execute(
            select(func.count(DocumentContent.id)).where(DocumentContent.content_text == unique_text)
        )).scalar()
        
        link_count = (await db.execute(
            select(func.count(ChunkReportLink.id)).where(
                ChunkReportLink.content_id.in_(
                    select(DocumentContent.id).where(DocumentContent.content_text == unique_text)
                )
            )
        )).scalar()
        
        print("\n--- FINAL VERDICT ---")
        print(f"Entries in DocumentContent: {content_count} (Should be 1)")
        print(f"Links in Junction Table: {link_count} (Should be 2)")
        
        if content_count == 1 and link_count == 2:
            print("\nSUCCESS: Deduplication is working perfectly across reports!")
        else:
            print("\nFAILED: Duplicate content was created.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_deduplication())
