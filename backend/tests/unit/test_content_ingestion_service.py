"""Unit tests for content_ingestion_service."""

import hashlib
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pipeline.content_ingestion_service import (
    _MAX_TOKENS,
    build_stock_scoped_content_hash,
    normalize_content_text,
    assemble_content_elements,
    persist_parsed_document,
    PersistedContentBatch,
)
from app.services.pipeline.document_parser import ParsedDocument, ParsedElement


class TestBuildStockScopedContentHash:
    def test_same_input_same_hash(self):
        h1 = build_stock_scoped_content_hash(1, "hello")
        h2 = build_stock_scoped_content_hash(1, "hello")
        assert h1 == h2

    def test_different_stock_different_hash(self):
        h1 = build_stock_scoped_content_hash(1, "hello")
        h2 = build_stock_scoped_content_hash(2, "hello")
        assert h1 != h2

    def test_normalization_applied(self):
        h1 = build_stock_scoped_content_hash(1, "  HELLO  ")
        h2 = build_stock_scoped_content_hash(1, "hello")
        assert h1 == h2

    def test_sha256_format(self):
        h = build_stock_scoped_content_hash(1, "test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestNormalizeContentText:
    def test_collapse_whitespace(self):
        assert normalize_content_text("a    b\nc") == "a b c"

    def test_strip(self):
        assert normalize_content_text("  text  ") == "text"

    def test_lowercase(self):
        assert normalize_content_text("HeLLo") == "hello"


class TestAssembleContentElements:
    def test_empty(self):
        doc = ParsedDocument(parser_version="v1", markdown="", elements=[])
        result = assemble_content_elements(doc, target_tokens=500)
        assert result == []

    def test_atomic_passed_through(self):
        doc = ParsedDocument(
            parser_version="v1",
            markdown="",
            elements=[
                ParsedElement(
                    element_type="heading",
                    text="Başlık",
                    markdown="## Başlık",
                    page_start=1,
                    page_end=1,
                    token_estimate=10,
                    is_atomic=True,
                ),
            ],
        )
        result = assemble_content_elements(doc, target_tokens=500)
        assert len(result) == 1
        assert result[0].element_type == "heading"

    def test_paragraphs_bundled(self):
        doc = ParsedDocument(
            parser_version="v1",
            markdown="",
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text="A",
                    markdown="A",
                    page_start=1,
                    page_end=1,
                    token_estimate=50,
                    is_atomic=False,
                ),
                ParsedElement(
                    element_type="paragraph",
                    text="B",
                    markdown="B",
                    page_start=1,
                    page_end=1,
                    token_estimate=50,
                    is_atomic=False,
                ),
            ],
        )
        result = assemble_content_elements(doc, target_tokens=500)
        assert len(result) == 1
        assert result[0].element_type == "paragraph_bundle"
        assert "A" in result[0].text
        assert "B" in result[0].text

    def test_split_by_section_path(self):
        doc = ParsedDocument(
            parser_version="v1",
            markdown="",
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text="A",
                    markdown="A",
                    page_start=1,
                    page_end=1,
                    section_path="S1",
                    token_estimate=50,
                    is_atomic=False,
                ),
                ParsedElement(
                    element_type="paragraph",
                    text="B",
                    markdown="B",
                    page_start=1,
                    page_end=1,
                    section_path="S2",
                    token_estimate=50,
                    is_atomic=False,
                ),
            ],
        )
        result = assemble_content_elements(doc, target_tokens=500)
        assert len(result) == 2


@pytest.mark.asyncio
class TestPersistParsedDocument:
    async def test_persists_elements(self):
        from app.models.kap_report import KapReport
        from app.models.document_content import DocumentContent

        kap_report = MagicMock(spec=KapReport)
        kap_report.id = 1
        kap_report.stock_id = 1
        kap_report.title = "Test Report"
        kap_report.filing_type = "FR"
        kap_report.summary = None
        kap_report.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        kap_report.local_pdf_path = None

        db = AsyncMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Mock execute results for deduplication lookups
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_scalar)

        doc = ParsedDocument(
            parser_version="v1",
            markdown="body",
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text="Hello world.",
                    markdown="Hello world.",
                    page_start=1,
                    page_end=1,
                    token_estimate=10,
                    is_atomic=False,
                ),
            ],
        )

        with patch(
            "app.services.pipeline.content_ingestion_service._write_markdown_snapshot",
            return_value="snap.md",
        ):
            result = await persist_parsed_document(db, kap_report, stock_id=1, parsed_document=doc)

        assert isinstance(result, PersistedContentBatch)
        assert result.linked_count >= 1

    async def test_splits_oversized_element(self):
        from app.models.kap_report import KapReport
        from app.models.document_content import DocumentContent

        kap_report = MagicMock(spec=KapReport)
        kap_report.id = 1
        kap_report.stock_id = 1
        kap_report.title = "Test"
        kap_report.filing_type = "FR"
        kap_report.summary = None
        kap_report.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        kap_report.local_pdf_path = None

        db = AsyncMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()

        # Track created DocumentContent objects so we can assign IDs
        _id_counter = [0]

        def mock_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

        db.execute = AsyncMock(side_effect=mock_execute)

        def mock_add(obj):
            if isinstance(obj, DocumentContent):
                _id_counter[0] += 1
                obj.id = _id_counter[0]

        db.add.side_effect = mock_add

        # Create a paragraph larger than 1024 tokens (~4096 chars)
        huge_text = "word " * 5000
        doc = ParsedDocument(
            parser_version="v1",
            markdown=huge_text,
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text=huge_text,
                    markdown=huge_text,
                    page_start=1,
                    page_end=1,
                    token_estimate=2000,  # > 1024
                    is_atomic=False,
                ),
            ],
        )

        with patch(
            "app.services.pipeline.content_ingestion_service._write_markdown_snapshot",
            return_value="snap.md",
        ):
            result = await persist_parsed_document(db, kap_report, stock_id=1, parsed_document=doc)

        # Should create at least a parent + one child
        assert result.created_count >= 2
        assert result.linked_count >= 2

    async def test_table_element_creates_extracted_table(self):
        from app.models.kap_report import KapReport
        from app.models.extracted_table import ExtractedTable

        kap_report = MagicMock(spec=KapReport)
        kap_report.id = 1
        kap_report.stock_id = 1
        kap_report.title = "Test"
        kap_report.filing_type = "FR"
        kap_report.summary = None
        kap_report.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        kap_report.local_pdf_path = None

        db = AsyncMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_scalar)

        doc = ParsedDocument(
            parser_version="v1",
            markdown="|a|b|",
            elements=[
                ParsedElement(
                    element_type="table",
                    text="|a|b|",
                    markdown="|a|b|",
                    page_start=1,
                    page_end=1,
                    token_estimate=10,
                    is_atomic=True,
                    table_data={"rows": 1},
                ),
            ],
        )

        with patch(
            "app.services.pipeline.content_ingestion_service._write_markdown_snapshot",
            return_value="snap.md",
        ):
            result = await persist_parsed_document(db, kap_report, stock_id=1, parsed_document=doc)

        # ExtractedTable should have been added via db.add
        calls = [c for c in db.add.call_args_list if isinstance(c.args[0], ExtractedTable)]
        assert len(calls) == 1
        assert calls[0].args[0].table_markdown == "|a|b|"
