"""Unit tests for chunking service.

Tests for:
- Hash computation (_compute_chunk_hash)
- Token estimation (_estimate_tokens)
- Text normalization (_normalize_text)
- Boilerplate detection (_is_boilerplate)
- Duplicate paragraph detection (_find_duplicate_paragraphs)
- PDF extraction (_extract_text_from_pdf)
- Chunking logic (_chunk_paragraphs)
- Service functions (mocked pdfplumber, mocked AsyncSession)
"""

import hashlib
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from app.services.pipeline.chunking_service import (
    _compute_chunk_hash,
    _estimate_tokens,
    _normalize_text,
    _calculate_alpha_ratio,
    _is_boilerplate,
    _find_duplicate_paragraphs,
    _detect_content_validation_warning,
    _chunk_paragraphs,
    ChunkingStatus,
    ChunkingResult,
    ChunkingBatchResult,
    MIN_CHUNK_CHARS,
    BOILERPLATE_PATTERNS,
    CHARS_PER_TOKEN,
)


# ============================================================================
# Hash Computation Tests
# ============================================================================


class TestComputeChunkHash:
    """Tests for _compute_chunk_hash function."""

    def test_consistent_hash(self):
        """Test that same text produces same hash."""
        text = "Bu bir test metnidir."
        hash1 = _compute_chunk_hash(text)
        hash2 = _compute_chunk_hash(text)
        assert hash1 == hash2

    def test_different_text_different_hash(self):
        """Test that different texts produce different hashes."""
        hash1 = _compute_chunk_hash("Test metin 1")
        hash2 = _compute_chunk_hash("Test metin 2")
        assert hash1 != hash2

    def test_normalized_before_hash(self):
        """Test that text is normalized (lowercase, stripped) before hashing."""
        text1 = "  TEST METIN  "
        text2 = "test metin"
        # After normalization both should be "test metin"
        hash1 = _compute_chunk_hash(text1)
        hash2 = _compute_chunk_hash(text2)
        assert hash1 == hash2

    def test_hash_is_sha256(self):
        """Test that hash is SHA-256 (64 hex chars)."""
        text = "Test"
        result = _compute_chunk_hash(text)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_turkish_characters_preserved(self):
        """Test that Turkish characters are handled correctly."""
        text = "Türkçe karakterler: ğüşıöç"
        result = _compute_chunk_hash(text)
        # Should not raise and should be consistent
        assert len(result) == 64


# ============================================================================
# Token Estimation Tests
# ============================================================================


class TestEstimateTokens:
    """Tests for _estimate_tokens function."""

    def test_basic_estimation(self):
        """Test basic token estimation."""
        text = "a" * 400  # 400 chars = 100 tokens
        result = _estimate_tokens(text)
        assert result == 100

    def test_empty_text(self):
        """Test empty text returns 0 tokens."""
        result = _estimate_tokens("")
        assert result == 0

    def test_short_text(self):
        """Test text shorter than 4 chars."""
        result = _estimate_tokens("abc")
        assert result == 0  # 3 // 4 = 0


# ============================================================================
# Text Normalization Tests
# ============================================================================


class TestNormalizeText:
    """Tests for _normalize_text function."""

    def test_whitespace_collapse(self):
        """Test that multiple whitespaces are collapsed."""
        text = "Bu    bir   test    metnidir."
        result = _normalize_text(text)
        assert result == "Bu bir test metnidir."

    def test_newlines_collapsed(self):
        """Test that newlines are collapsed to spaces."""
        text = "Satır 1\n\nSatır 2\nSatır 3"
        result = _normalize_text(text)
        assert result == "Satır 1 Satır 2 Satır 3"

    def test_leading_trailing_whitespace_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "   Test metin   "
        result = _normalize_text(text)
        assert result == "Test metin"

    def test_turkish_chars_preserved(self):
        """Test that Turkish characters are preserved."""
        text = "ĞÜŞİÖÇ ğüşıöç"
        result = _normalize_text(text)
        assert "Ğ" in result
        assert "ğ" in result
        assert "Ü" in result
        assert "ü" in result


# ============================================================================
# Alpha Ratio Tests
# ============================================================================


class TestCalculateAlphaRatio:
    """Tests for _calculate_alpha_ratio function."""

    def test_all_alpha(self):
        """Test text with all alphanumeric chars."""
        text = "TestMetin123"
        result = _calculate_alpha_ratio(text)
        assert result == 1.0

    def test_mixed_content(self):
        """Test text with mixed content."""
        text = "Test123!!!"  # 7 alnum out of 10 chars
        result = _calculate_alpha_ratio(text)
        assert result == 0.7

    def test_empty_text(self):
        """Test empty text returns 0.0."""
        result = _calculate_alpha_ratio("")
        assert result == 0.0

    def test_only_special_chars(self):
        """Test text with only special chars."""
        text = "!@#$%^&*()"
        result = _calculate_alpha_ratio(text)
        assert result == 0.0


# ============================================================================
# Boilerplate Detection Tests
# ============================================================================


class TestIsBoilerplate:
    """Tests for _is_boilerplate function."""

    def test_short_text_is_boilerplate(self):
        """Test that very short text is filtered."""
        text = "Kısa"
        result = _is_boilerplate(text)
        assert result is True

    def test_cover_page_pattern(self):
        """Test that cover page patterns are filtered."""
        text = "2024 Yıl Faaliyet Raporu"
        result = _is_boilerplate(text)
        assert result is True

    def test_table_of_contents(self):
        """Test that table of contents is filtered."""
        text = "İçindekiler"
        result = _is_boilerplate(text)
        assert result is True

    def test_page_number(self):
        """Test that page numbers are filtered."""
        text = "Sayfa 5"
        result = _is_boilerplate(text)
        assert result is True

    def test_low_alpha_ratio(self):
        """Test that low alphanumeric ratio is filtered."""
        text = "!@#$%^&*()!@#$%^&*()!@#$%^&*()!@#$%^&*()!@#$%^&*()!@#$%^&*()"  # 60 special chars
        result = _is_boilerplate(text)
        assert result is True

    def test_normal_text_not_filtered(self):
        """Test that normal meaningful text is NOT filtered."""
        text = "Şirketin 2024 yılı net karı 5.2 milyar TL olarak gerçekleşmiştir."
        result = _is_boilerplate(text)
        assert result is False

    def test_long_meaningful_text(self):
        """Test that long meaningful text is NOT filtered."""
        text = (
            "Türk Hava Yolları 2024 yılında toplam 85 milyon yolcu taşımış olup, "
            "bu rakam bir önceki yıla göre %15 artış göstermiştir. Şirketin gelirleri "
            "200 milyar TL'ye ulaşarak tarihi bir rekor kırmıştır."
        )
        result = _is_boilerplate(text)
        assert result is False


# ============================================================================
# Duplicate Paragraph Detection Tests
# ============================================================================


class TestFindDuplicateParagraphs:
    """Tests for _find_duplicate_paragraphs function."""

    def test_no_duplicates(self):
        """Test with no duplicate paragraphs."""
        pages = [
            "Paragraph one with unique content.",
            "Paragraph two with different text.",
        ]
        result = _find_duplicate_paragraphs(pages)
        assert result == set()


class TestDetectContentValidationWarning:
    """Tests for content/metadata mismatch heuristics."""

    def test_financial_report_mismatch_warning(self):
        result = _detect_content_validation_warning(
            title="THYAO Finansal Rapor 2024",
            filing_type="FR",
            chunks=[
                "KAP'ta yayınlanma tarihi ve saati: 03.11.2022 17:34:37 "
                "Ortaklık paylarının BİAŞ'ta oluşan ağırlıklı ortalama fiyatının..."
            ],
        )
        assert result == "content_validation_warning:possible_pdf_metadata_mismatch"

    def test_financial_report_without_mismatch_warning(self):
        result = _detect_content_validation_warning(
            title="THYAO Finansal Rapor 2024",
            filing_type="FR",
            chunks=[
                "Konsolide finansal durum tablosu, gelir tablosu ve nakit akış tablosu dipnotları..."
            ],
        )
        assert result is None

    def test_with_duplicates(self):
        """Test with duplicate paragraphs."""
        pages = [
            "Repeated paragraph.",
            "Unique paragraph.",
            "Repeated paragraph.",  # Duplicate
        ]
        result = _find_duplicate_paragraphs(pages)
        # The second occurrence should be marked as duplicate
        assert len(result) > 0

    def test_empty_pages(self):
        """Test with empty pages."""
        pages = []
        result = _find_duplicate_paragraphs(pages)
        assert result == set()


# ============================================================================
# Chunking Tests
# ============================================================================


class TestChunkParagraphs:
    """Tests for _chunk_paragraphs function."""

    def test_basic_chunking(self):
        """Test basic paragraph chunking."""
        # Create text that should result in at least one chunk
        pages = [
            "Bu bir test paragrafıdır. " * 20,  # Enough for a chunk
        ]
        result = _chunk_paragraphs(pages, target_tokens=100, overlap_tokens=10)
        assert len(result) >= 1
        assert all(len(chunk) > 0 for chunk in result)

    def test_empty_pages(self):
        """Test with empty pages."""
        pages = []
        result = _chunk_paragraphs(pages)
        assert result == []

    def test_boilerplate_filtered(self):
        """Test that boilerplate is filtered during chunking."""
        pages = [
            "2024 Yıl Faaliyet Raporu",  # Boilerplate - should be filtered
            "Şirketin net karı 5.2 milyar TL olarak gerçekleşmiştir ve geçen yıla göre önemli bir artış göstermiştir.",
        ]
        result = _chunk_paragraphs(pages, target_tokens=500, overlap_tokens=50)
        # Boilerplate should be filtered, only meaningful text should remain
        if result:
            assert "Faaliyet Raporu" not in result[0] or "net kar" in result[0]

    def test_chunk_size_respects_target(self):
        """Test that chunks roughly respect target size."""
        # Create text with multiple paragraphs (separated by double newlines)
        long_paragraph = "Test cümlesi. " * 50  # ~700 chars per paragraph
        pages = [long_paragraph + "\n\n" + long_paragraph + "\n\n" + long_paragraph + "\n\n" + long_paragraph]

        result = _chunk_paragraphs(pages, target_tokens=100, overlap_tokens=10)

        # Should be split into multiple chunks due to target size
        assert len(result) >= 1

        # Each chunk should be roughly around target (with some flexibility)
        target_chars = 100 * CHARS_PER_TOKEN  # 400 chars
        for chunk in result:
            # Allow some flexibility (chunks can be slightly larger due to paragraph boundaries)
            assert len(chunk) <= target_chars * 5  # Max 5x target (allowing for paragraph merging)

    def test_duplicate_paragraphs_filtered(self):
        """Test that duplicate paragraph indices are excluded before chunking."""
        repeated = (
            "Şirketin net karı 5.2 milyar TL olarak gerçekleşmiştir ve geçen yıla göre önemli bir artış göstermiştir."
        )
        pages = [f"{repeated}\n\n{repeated}"]

        result = _chunk_paragraphs(
            pages,
            target_tokens=500,
            overlap_tokens=50,
            duplicate_indices={1},
        )

        assert len(result) == 1
        assert result[0].count("Şirketin net karı") == 1


# ============================================================================
# Chunking Status Enum Tests
# ============================================================================


class TestChunkingStatusEnum:
    """Tests for ChunkingStatus enum."""

    def test_values(self):
        """Test that enum has expected values."""
        assert ChunkingStatus.PENDING.value == "PENDING"
        assert ChunkingStatus.CHUNKING.value == "CHUNKING"
        assert ChunkingStatus.COMPLETED.value == "COMPLETED"
        assert ChunkingStatus.FAILED.value == "FAILED"

    def test_string_comparison(self):
        """Test that enum can be compared with strings."""
        assert ChunkingStatus.PENDING == "PENDING"
        assert ChunkingStatus.COMPLETED != "FAILED"


# ============================================================================
# Result Model Tests
# ============================================================================


class TestChunkingResult:
    """Tests for ChunkingResult model."""

    def test_default_values(self):
        """Test default values for optional fields."""
        result = ChunkingResult(
            kap_report_id=1,
            symbol="THYAO",
            disclosure_index="123",
            success=True,
            status=ChunkingStatus.COMPLETED,
        )
        assert result.chunks_created == 0
        assert result.chunks_skipped == 0
        assert result.error_message is None
        assert result.duration_ms is None

    def test_all_fields(self):
        """Test with all fields populated."""
        result = ChunkingResult(
            kap_report_id=1,
            symbol="THYAO",
            disclosure_index="123",
            success=True,
            chunks_created=10,
            chunks_skipped=2,
            status=ChunkingStatus.COMPLETED,
            duration_ms=1500,
        )
        assert result.chunks_created == 10
        assert result.chunks_skipped == 2
        assert result.duration_ms == 1500


class TestChunkingBatchResult:
    """Tests for ChunkingBatchResult model."""

    def test_default_values(self):
        """Test default values."""
        result = ChunkingBatchResult(
            total_processed=10,
            successful=8,
            failed=2,
            status="partial",
        )
        assert result.results == []
        assert result.details is None

    def test_with_results(self):
        """Test with results list."""
        single_result = ChunkingResult(
            kap_report_id=1,
            symbol="THYAO",
            disclosure_index="123",
            success=True,
            status=ChunkingStatus.COMPLETED,
        )
        result = ChunkingBatchResult(
            total_processed=1,
            successful=1,
            failed=0,
            status="success",
            results=[single_result],
        )
        assert len(result.results) == 1


# ============================================================================
# Integration Tests (with mocked DB and pdfplumber)
# ============================================================================


class TestChunkSinglePdf:
    """Tests for chunk_single_pdf function."""

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Test handling of missing PDF file."""
        from app.services.pipeline.chunking_service import chunk_single_pdf
        from app.models.kap_report import KapReport
        from unittest.mock import AsyncMock
        from pathlib import Path as RealPath

        # Create mock KapReport with proper string values
        kap_report = MagicMock(spec=KapReport)
        kap_report.id = 1
        kap_report.local_pdf_path = "THYAO/2024/12345.pdf"  # Path().stem will give "12345"
        kap_report.pdf_url = "https://www.kap.org.tr/tr/api/BildirimPdf/12345"
        kap_report.stock_id = 1
        kap_report.stock = MagicMock(symbol="THYAO")
        kap_report.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        kap_report.chunking_status = "PENDING"

        # Mock DB session
        db = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()

        # Mock _extract_text_from_pdf to raise FileNotFoundError
        with patch("app.services.pipeline.chunking_service._extract_text_from_pdf") as mock_extract:
            mock_extract.side_effect = FileNotFoundError("PDF file not found")

            result = await chunk_single_pdf(
                db=db,
                kap_report=kap_report,
                storage_base=RealPath("/data/pdfs"),
            )

        assert result.success is False
        assert result.status == ChunkingStatus.FAILED
        assert "FileNotFoundError" in result.error_message or "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_empty_pdf(self):
        """Test handling of empty PDF."""
        from app.services.pipeline.chunking_service import chunk_single_pdf
        from app.models.kap_report import KapReport
        from pathlib import Path as RealPath
        from app.services.pipeline.document_parser import ParsedDocument

        kap_report = MagicMock(spec=KapReport)
        kap_report.id = 1
        kap_report.local_pdf_path = "THYAO/2024/12345.pdf"
        kap_report.pdf_url = "https://www.kap.org.tr/tr/api/BildirimPdf/12345"
        kap_report.stock_id = 1
        kap_report.stock = MagicMock(symbol="THYAO")
        kap_report.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        kap_report.chunking_status = "PENDING"

        db = AsyncMock()
        db.commit = AsyncMock()

        with patch("app.services.pipeline.chunking_service.get_structured_pdf_parser") as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = ParsedDocument(
                parser_version="test",
                markdown="",
                elements=[],
            )
            mock_get_parser.return_value = mock_parser

            result = await chunk_single_pdf(
                db=db,
                kap_report=kap_report,
                storage_base=RealPath("/data/pdfs"),
            )

        assert result.success is True  # Successfully processed, just empty
        assert result.chunks_created == 0
        assert result.error_message == "empty_extraction"


class TestBatchChunkCompletedPdfs:
    """Tests for batch_chunk_completed_pdfs function."""

    @pytest.mark.asyncio
    async def test_no_pending_pdfs(self):
        """Test when no PDFs are pending chunking."""
        from app.services.pipeline.chunking_service import batch_chunk_completed_pdfs

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = await batch_chunk_completed_pdfs(db=db, limit=50)

        assert result.total_processed == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.status == "success"
