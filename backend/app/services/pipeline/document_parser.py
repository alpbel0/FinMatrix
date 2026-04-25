"""Structured PDF parsing abstraction for RAG 2.0.

Uses Docling DOM Parser as the primary backend to extract hierarchical
sections, tables, and paragraphs. Falls back to pdfplumber if Docling
is unavailable or raises an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pdfplumber

from app.services.pipeline.sentence_splitter import split_text_into_chunks
from app.services.utils.logging import logger


class ParserUnavailableError(RuntimeError):
    """Raised when the requested parser backend is not available."""


@dataclass(slots=True)
class ParsedElement:
    element_type: str  # heading | paragraph | table | list
    text: str
    markdown: str
    page_start: int
    page_end: int
    section_path: str = ""
    token_estimate: int = 0
    is_atomic: bool = False
    is_summary_prefix: bool = False
    is_synthetic: bool = False
    content_origin: str = "pdf_docling"
    table_data: dict[str, Any] | None = None  # Only for tables


@dataclass(slots=True)
class ParsedDocument:
    parser_version: str
    markdown: str
    elements: list[ParsedElement] = field(default_factory=list)
    tables: list[ParsedElement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class StructuredPdfParser(Protocol):
    parser_version: str

    def parse(self, pdf_path: Path) -> ParsedDocument:
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token estimator for Turkish text (1 token ≈ 4 chars)."""
    return max(len(text) // 4, 1)


def _sanitize_section_path(text: str) -> str:
    """Clean section path for use in context prepend and metadata."""
    if not text:
        return ""
    cleaned = text.replace("\n", " ").replace("\t", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()[:500]


# ---------------------------------------------------------------------------
# Docling DOM Parser
# ---------------------------------------------------------------------------


class DoclingDomParser:
    parser_version = "docling_dom_v2"

    def parse(self, pdf_path: Path) -> ParsedDocument:
        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.base_models import ConversionStatus
        except ImportError as exc:
            raise ParserUnavailableError("docling is not installed") from exc

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))

        if result.status == ConversionStatus.FAILURE:
            raise RuntimeError(f"Docling conversion failed for {pdf_path}")

        document = result.document
        elements: list[ParsedElement] = []
        tables: list[ParsedElement] = []
        section_stack: list[str] = []
        current_section_path = ""

        # Process text items (paragraphs, headings, lists)
        for item in document.texts:
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue

            label = str(getattr(item, "label", "paragraph")).lower()
            prov = getattr(item, "prov", None)
            page_no = prov[0].page_no if prov and len(prov) > 0 else 1

            if "heading" in label or "section_header" in label:
                # Update section stack: treat every heading as a flat section switch
                # (Docling does not expose heading levels consistently, so we use a
                # simple single-level stack. Future: enhance with level detection.)
                heading_text = _sanitize_section_path(text)
                if heading_text:
                    section_stack = [heading_text]
                    current_section_path = heading_text

                elements.append(
                    ParsedElement(
                        element_type="heading",
                        text=text,
                        markdown=f"## {text}",
                        page_start=page_no,
                        page_end=page_no,
                        section_path=current_section_path,
                        token_estimate=_estimate_tokens(text),
                        is_atomic=True,
                        content_origin="pdf_docling",
                    )
                )
            elif "list" in label:
                elements.append(
                    ParsedElement(
                        element_type="list",
                        text=text,
                        markdown=text,
                        page_start=page_no,
                        page_end=page_no,
                        section_path=current_section_path,
                        token_estimate=_estimate_tokens(text),
                        is_atomic=True,
                        content_origin="pdf_docling",
                    )
                )
            else:
                # Paragraph / other text
                elements.append(
                    ParsedElement(
                        element_type="paragraph",
                        text=text,
                        markdown=text,
                        page_start=page_no,
                        page_end=page_no,
                        section_path=current_section_path,
                        token_estimate=_estimate_tokens(text),
                        is_atomic=False,
                        content_origin="pdf_docling",
                    )
                )

        # Process tables separately
        for table in document.tables:
            table_md = ""
            table_json: dict[str, Any] | None = None
            try:
                # Try to get markdown representation
                if hasattr(table, "export_to_markdown"):
                    table_md = table.export_to_markdown(doc=document) or ""
                # Try to get DataFrame and convert to JSON
                if hasattr(table, "export_to_dataframe"):
                    df = table.export_to_dataframe(doc=document)
                    if df is not None:
                        table_json = df.to_dict(orient="records")
                        if not table_md:
                            table_md = df.to_markdown(index=False)
            except Exception as exc:
                logger.warning(f"Docling table extraction failed: {exc}")
                table_md = ""

            if not table_md:
                # Fallback: use text representation if available
                table_md = getattr(table, "text", "") or ""

            prov = getattr(table, "prov", None)
            page_no = prov[0].page_no if prov and len(prov) > 0 else 1

            table_element = ParsedElement(
                element_type="table",
                text=table_md,
                markdown=table_md,
                page_start=page_no,
                page_end=page_no,
                section_path=current_section_path,
                token_estimate=_estimate_tokens(table_md),
                is_atomic=True,
                content_origin="pdf_docling",
                table_data=table_json,
            )
            elements.append(table_element)
            tables.append(table_element)

        # Build full markdown snapshot
        md_parts: list[str] = []
        for el in elements:
            if el.element_type == "heading":
                md_parts.append(el.markdown)
            elif el.element_type == "table":
                md_parts.append(el.markdown)
            else:
                md_parts.append(el.text)

        return ParsedDocument(
            parser_version=self.parser_version,
            markdown="\n\n".join(md_parts),
            elements=elements,
            tables=tables,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# pdfplumber Fallback Parser
# ---------------------------------------------------------------------------


class PdfPlumberFallbackParser:
    parser_version = "pdfplumber_fallback_v2"

    def parse(self, pdf_path: Path) -> ParsedDocument:
        pages: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")

        markdown_parts: list[str] = []
        elements: list[ParsedElement] = []
        current_section = ""

        for page_number, page_text in enumerate(pages, start=1):
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", page_text) if part.strip()]
            for paragraph in paragraphs:
                normalized = re.sub(r"\s+", " ", paragraph).strip()
                if not normalized:
                    continue

                if _looks_like_heading(normalized):
                    current_section = _sanitize_section_path(normalized)
                    markdown = f"## {normalized}"
                    element_type = "heading"
                    is_atomic = True
                else:
                    markdown = normalized
                    element_type = "paragraph"
                    is_atomic = False

                markdown_parts.append(markdown)
                elements.append(
                    ParsedElement(
                        element_type=element_type,
                        text=normalized,
                        markdown=markdown,
                        page_start=page_number,
                        page_end=page_number,
                        section_path=current_section,
                        token_estimate=_estimate_tokens(normalized),
                        is_atomic=is_atomic,
                        content_origin="pdf_docling" if element_type == "heading" else "pdf_docling",
                    )
                )

        return ParsedDocument(
            parser_version=self.parser_version,
            markdown="\n\n".join(markdown_parts),
            elements=elements,
            tables=[],
            warnings=["docling_unavailable_fallback"],
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_structured_pdf_parser(backend: str | None = None) -> StructuredPdfParser:
    from app.config import get_settings

    if backend is None:
        backend = get_settings().document_parser_backend.lower().strip()

    if backend == "docling":
        try:
            return DoclingDomParser()
        except ParserUnavailableError:
            logger.warning("Docling parser unavailable, falling back to pdfplumber")
            return PdfPlumberFallbackParser()

    return PdfPlumberFallbackParser()


# ---------------------------------------------------------------------------
# Summary prefix helper
# ---------------------------------------------------------------------------


def prepend_summary_element(document: ParsedDocument, summary: str | None) -> ParsedDocument:
    if not summary or not summary.strip():
        return document

    normalized = re.sub(r"\s+", " ", summary).strip()
    if not normalized:
        return document

    summary_element = ParsedElement(
        element_type="summary_prefix",
        text=normalized,
        markdown=f"> Summary\n>\n> {normalized}",
        page_start=0,
        page_end=0,
        section_path="Summary",
        token_estimate=_estimate_tokens(normalized),
        is_atomic=True,
        is_summary_prefix=True,
        content_origin="kap_summary",
    )
    return ParsedDocument(
        parser_version=document.parser_version,
        markdown=f"{summary_element.markdown}\n\n{document.markdown}".strip(),
        elements=[summary_element, *document.elements],
        tables=document.tables,
        warnings=document.warnings,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _looks_like_heading(text: str) -> bool:
    if len(text) > 120:
        return False
    if text.endswith(":"):
        return True
    alpha_ratio = sum(1 for char in text if char.isalpha()) / max(len(text), 1)
    return alpha_ratio > 0.6 and (text.isupper() or text.istitle())
