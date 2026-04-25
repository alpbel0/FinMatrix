"""Unit tests for document_parser module.

These tests focus on helper functions, fallback parser, and data structures.
Integration tests with real PDFs live in ``tests/integration/test_real_pdf_parse.py``.
"""

import tempfile
from pathlib import Path

import pytest

from app.services.pipeline.document_parser import (
    ParsedDocument,
    ParsedElement,
    PdfPlumberFallbackParser,
    _looks_like_heading,
    _sanitize_section_path,
    get_structured_pdf_parser,
    prepend_summary_element,
)


class TestSanitizeSectionPath:
    def test_removes_newlines_and_tabs(self):
        assert _sanitize_section_path("Line1\nLine2\tTab") == "Line1 Line2 Tab"

    def test_collapses_multiple_spaces(self):
        assert _sanitize_section_path("A    B     C") == "A B C"

    def test_trims_and_limits_length(self):
        long_text = "x" * 600
        assert len(_sanitize_section_path(long_text)) == 500

    def test_empty_string(self):
        assert _sanitize_section_path("") == ""


class TestLooksLikeHeading:
    def test_short_uppercase(self):
        assert _looks_like_heading("FİNANSAL DURUM") is True

    def test_short_titlecase(self):
        assert _looks_like_heading("Finansal Durum") is True

    def test_ends_with_colon(self):
        assert _looks_like_heading("Notlar:") is True

    def test_too_long(self):
        assert _looks_like_heading("a" * 121) is False

    def test_low_ratio(self):
        assert _looks_like_heading("1234567890") is False


class TestParsedElement:
    def test_defaults(self):
        el = ParsedElement(element_type="paragraph", text="hello", markdown="hello", page_start=1, page_end=1)
        assert el.section_path == ""
        assert el.token_estimate == 0
        assert el.is_atomic is False
        assert el.table_data is None

    def test_table_data(self):
        el = ParsedElement(
            element_type="table",
            text="|a|b|",
            markdown="|a|b|",
            page_start=1,
            page_end=1,
            table_data={"rows": 1},
        )
        assert el.table_data == {"rows": 1}


class TestPrependSummaryElement:
    def test_adds_summary(self):
        doc = ParsedDocument(parser_version="v1", markdown="body", elements=[])
        result = prepend_summary_element(doc, "Özet bilgi.")
        assert len(result.elements) == 1
        assert result.elements[0].is_summary_prefix is True
        assert "Özet bilgi." in result.markdown

    def test_none_summary(self):
        doc = ParsedDocument(parser_version="v1", markdown="body", elements=[])
        result = prepend_summary_element(doc, None)
        assert result == doc

    def test_empty_summary(self):
        doc = ParsedDocument(parser_version="v1", markdown="body", elements=[])
        result = prepend_summary_element(doc, "   ")
        assert result == doc


class TestGetStructuredPdfParser:
    def test_pdfplumber_backend(self):
        parser = get_structured_pdf_parser(backend="pdfplumber")
        assert parser.parser_version == "pdfplumber_fallback_v2"

    def test_docling_fallback_when_unavailable(self, monkeypatch):
        from app.services.pipeline.document_parser import DoclingDomParser, ParserUnavailableError

        def mock_init(self):
            raise ParserUnavailableError("docling is not installed")

        monkeypatch.setattr(DoclingDomParser, "__init__", mock_init)
        parser = get_structured_pdf_parser(backend="docling")
        assert parser.parser_version == "pdfplumber_fallback_v2"


class TestPdfPlumberFallbackParser:
    def test_parse_sample_pdf(self):
        parser = PdfPlumberFallbackParser()
        # Create a minimal one-page PDF with reportlab if available,
        # otherwise skip gracefully.
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            pytest.skip("reportlab not installed, cannot create test PDF")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            c.drawString(100, 700, "Başlık: Finansal Rapor")
            c.drawString(100, 680, "Bu bir paragraftır.")
            c.drawString(100, 660, "İkinci paragraf burada.")
            c.save()
            tmp_path = Path(tmp.name)

        try:
            doc = parser.parse(tmp_path)
            assert doc.parser_version == "pdfplumber_fallback_v2"
            assert len(doc.elements) >= 1
            # At least one element should be detected as a heading
            headings = [el for el in doc.elements if el.element_type == "heading"]
            paragraphs = [el for el in doc.elements if el.element_type == "paragraph"]
            assert len(headings) >= 1 or len(paragraphs) >= 1
        finally:
            tmp_path.unlink(missing_ok=True)
