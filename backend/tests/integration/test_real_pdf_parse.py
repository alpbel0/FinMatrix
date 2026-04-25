"""Integration tests for real PDF parsing with Docling DOM Parser.

These tests use:
- Real PostgreSQL test DB (finmatrix_test) via Alembic migrations
- Real PDF fixtures under tests/fixtures/
- Golden files under tests/fixtures/golden/ for regression checks

Run with:
    cd backend && python -m pytest tests/integration/test_real_pdf_parse.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_content import DocumentContent
from app.models.extracted_table import ExtractedTable
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.pipeline.document_parser import DoclingDomParser, PdfPlumberFallbackParser, get_structured_pdf_parser
from app.services.pipeline.content_ingestion_service import persist_parsed_document


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"
PDF_FILES = sorted(FIXTURE_DIR.glob("*.pdf"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_golden(pdf_path: Path) -> dict:
    golden_path = GOLDEN_DIR / f"{pdf_path.stem}.json"
    if not golden_path.exists():
        pytest.skip(f"Golden file not found: {golden_path.name}")
    return json.loads(golden_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Module-scoped cache: Docling parsing is CPU-heavy; parse once, reuse.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def parsed_docs():
    """Parse all PDF fixtures once with the primary structured parser."""
    docs = {}
    for pdf_path in PDF_FILES:
        parser = get_structured_pdf_parser()
        docs[pdf_path] = parser.parse(pdf_path)
    return docs


# ---------------------------------------------------------------------------
# PdfPlumber fallback (always available)
# ---------------------------------------------------------------------------


class TestPdfPlumberFallbackParser:
    def test_parse_sample_pdf(self):
        for pdf_path in PDF_FILES:
            parser = PdfPlumberFallbackParser()
            doc = parser.parse(pdf_path)
            assert doc.parser_version == "pdfplumber_fallback_v2"
            assert len(doc.elements) > 0
            for el in doc.elements:
                assert el.text
                assert el.page_start > 0


# ---------------------------------------------------------------------------
# Docling DOM Parser (requires docling installed)
# ---------------------------------------------------------------------------


try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


@pytest.mark.skipif(not DOCLING_AVAILABLE, reason="docling not installed")
class TestDoclingDomParser:
    def test_parse_sample_elements(self, parsed_docs):
        for pdf_path in PDF_FILES:
            doc = parsed_docs[pdf_path]
            assert doc.parser_version == "docling_dom_v2"
            assert len(doc.elements) > 0

    def test_parse_against_golden(self, parsed_docs):
        """Regression test: current parser output must match golden file."""
        for pdf_path in PDF_FILES:
            golden = _load_golden(pdf_path)
            doc = parsed_docs[pdf_path]

            assert doc.parser_version == golden["parser_version"]
            assert len(doc.elements) == golden["element_count"]
            assert len(doc.tables) == golden["table_count"]
            assert doc.warnings == golden["warnings"]

            for idx, el in enumerate(doc.elements):
                golden_el = golden["elements"][idx]
                assert el.element_type == golden_el["element_type"]
                assert el.text == golden_el["text"]
                assert el.section_path == golden_el["section_path"]
                assert el.is_atomic == golden_el["is_atomic"]
                assert (el.table_data is not None) == golden_el["has_table_data"]

    def test_tables_extracted(self, parsed_docs):
        for pdf_path in PDF_FILES:
            doc = parsed_docs[pdf_path]
            for table in doc.tables:
                assert table.element_type == "table"
                assert table.markdown

    def test_heading_detection(self, parsed_docs):
        for pdf_path in PDF_FILES:
            doc = parsed_docs[pdf_path]
            headings = [el for el in doc.elements if el.element_type == "heading"]
            for h in headings:
                assert h.text
                assert h.is_atomic is True


# ---------------------------------------------------------------------------
# Real DB persistence tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DOCLING_AVAILABLE, reason="docling not installed")
class TestPersistToRealDb:
    @pytest.mark.asyncio
    async def test_persist_parsed_document_creates_rows(self, db_session: AsyncSession, parsed_docs):
        """End-to-end: parse a real PDF and persist to the test DB."""
        if not PDF_FILES:
            pytest.skip("No PDF fixtures found")

        pdf_path = PDF_FILES[0]
        parsed_doc = parsed_docs[pdf_path]

        # Seed a stock and kap_report so FK constraints are happy
        stock = Stock(symbol="THYAO", company_name="Test", sector="Test", exchange="BIST", is_active=True)
        db_session.add(stock)
        await db_session.flush()

        kap_report = KapReport(
            stock_id=stock.id,
            title="Test Report",
            filing_type="FR",
            source_url="https://kap.org.tr/1",
            published_at=None,
            local_pdf_path=None,
        )
        db_session.add(kap_report)
        await db_session.flush()

        result = await persist_parsed_document(
            db=db_session,
            kap_report=kap_report,
            stock_id=stock.id,
            parsed_document=parsed_doc,
        )

        await db_session.commit()

        assert result.linked_count > 0

        # Verify DocumentContent rows exist
        content_result = await db_session.execute(
            select(DocumentContent).where(DocumentContent.stock_id == stock.id)
        )
        contents = content_result.scalars().all()
        assert len(contents) > 0

        # Verify ExtractedTable rows exist if tables were present
        if parsed_doc.tables:
            table_result = await db_session.execute(
                select(ExtractedTable).where(ExtractedTable.kap_report_id == kap_report.id)
            )
            tables = table_result.scalars().all()
            assert len(tables) > 0

    @pytest.mark.asyncio
    async def test_persist_oversized_element_splits(self, db_session: AsyncSession, parsed_docs):
        """1024-token safety wall: oversized blocks are split into parent+children."""
        if not PDF_FILES:
            pytest.skip("No PDF fixtures found")

        pdf_path = PDF_FILES[0]
        parsed_doc = parsed_docs[pdf_path]

        stock = Stock(symbol="SPLIT", company_name="Test", sector="Test", exchange="BIST", is_active=True)
        db_session.add(stock)
        await db_session.flush()

        kap_report = KapReport(
            stock_id=stock.id,
            title="Split Test",
            filing_type="FR",
            source_url="https://kap.org.tr/2",
            published_at=None,
            local_pdf_path=None,
        )
        db_session.add(kap_report)
        await db_session.flush()

        result = await persist_parsed_document(
            db=db_session,
            kap_report=kap_report,
            stock_id=stock.id,
            parsed_document=parsed_doc,
        )
        await db_session.commit()

        # If any element exceeded 1024 tokens, we expect parent_content_id to be populated
        content_result = await db_session.execute(
            select(DocumentContent).where(DocumentContent.stock_id == stock.id)
        )
        contents = content_result.scalars().all()
        assert len(contents) > 0

        child_contents = [c for c in contents if c.parent_content_id is not None]
        if any(el.token_estimate > 1024 and not el.is_atomic for el in parsed_doc.elements):
            assert len(child_contents) > 0
