"""Structured PDF parsing abstraction for RAG 2.0."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pdfplumber

from app.config import get_settings
from app.services.utils.logging import logger


class ParserUnavailableError(RuntimeError):
    """Raised when the requested parser backend is not available."""


@dataclass(slots=True)
class ParsedElement:
    element_type: str
    text: str
    markdown: str
    page_start: int
    page_end: int
    section_path: str = ""
    token_estimate: int = 0
    is_atomic: bool = False
    is_summary_prefix: bool = False
    content_origin: str = "pdf_docling"


@dataclass(slots=True)
class ParsedDocument:
    parser_version: str
    markdown: str
    elements: list[ParsedElement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class StructuredPdfParser(Protocol):
    parser_version: str

    def parse(self, pdf_path: Path) -> ParsedDocument:
        ...


class DoclingMarkdownParser:
    parser_version = "docling_markdown_v1"

    def parse(self, pdf_path: Path) -> ParsedDocument:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ParserUnavailableError("docling is not installed") from exc

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        document = result.document
        markdown = document.export_to_markdown()
        elements = _build_elements_from_markdown(markdown, parser_version=self.parser_version)
        return ParsedDocument(
            parser_version=self.parser_version,
            markdown=markdown,
            elements=elements,
        )


class PdfPlumberMarkdownParser:
    parser_version = "pdfplumber_markdown_v1"

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
                    current_section = normalized[:500]
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
                        token_estimate=max(len(normalized) // 4, 1),
                        is_atomic=is_atomic,
                        content_origin="pdf_docling" if element_type == "heading" else "pdf_docling",
                    )
                )

        return ParsedDocument(
            parser_version=self.parser_version,
            markdown="\n\n".join(markdown_parts),
            elements=elements,
            warnings=["docling_unavailable_fallback"] if elements else [],
        )


def get_structured_pdf_parser() -> StructuredPdfParser:
    settings = get_settings()
    backend = settings.document_parser_backend.lower().strip()

    if backend == "docling":
        try:
            return DoclingMarkdownParser()
        except ParserUnavailableError:
            logger.warning("Docling parser unavailable, falling back to pdfplumber markdown parser")
            return PdfPlumberMarkdownParser()

    return PdfPlumberMarkdownParser()


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
        token_estimate=max(len(normalized) // 4, 1),
        is_atomic=True,
        is_summary_prefix=True,
        content_origin="kap_summary",
    )
    return ParsedDocument(
        parser_version=document.parser_version,
        markdown=f"{summary_element.markdown}\n\n{document.markdown}".strip(),
        elements=[summary_element, *document.elements],
        warnings=document.warnings,
    )


def _looks_like_heading(text: str) -> bool:
    if len(text) > 120:
        return False
    if text.endswith(":"):
        return True
    alpha_ratio = sum(1 for char in text if char.isalpha()) / max(len(text), 1)
    return alpha_ratio > 0.6 and (text.isupper() or text.istitle())


def _build_elements_from_markdown(markdown: str, parser_version: str) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    current_section = ""

    for index, block in enumerate(re.split(r"\n\s*\n", markdown), start=1):
        normalized = block.strip()
        if not normalized:
            continue

        if normalized.startswith("#"):
            heading_text = normalized.lstrip("#").strip()
            current_section = heading_text[:500]
            element_type = "heading"
            is_atomic = True
            plain_text = heading_text
        elif normalized.startswith("|"):
            element_type = "table"
            is_atomic = True
            plain_text = normalized
        elif normalized.startswith("-") or normalized.startswith("*"):
            element_type = "list"
            is_atomic = True
            plain_text = normalized
        else:
            element_type = "paragraph"
            is_atomic = False
            plain_text = normalized

        elements.append(
            ParsedElement(
                element_type=element_type,
                text=plain_text,
                markdown=normalized,
                page_start=index,
                page_end=index,
                section_path=current_section,
                token_estimate=max(len(plain_text) // 4, 1),
                is_atomic=is_atomic,
                content_origin="pdf_docling",
            )
        )

    return elements
