"""Content-centric extraction and persistence for RAG 2.0.

Handles:
- Deduplicated DocumentContent creation
- ExtractedTable persistence for table elements
- 1024-token safety split with parent-child linking
- Legacy DocumentChunk backward-compatibility
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chunk_report_link import ChunkReportLink
from app.models.document_content import DocumentContent
from app.models.document_chunk import DocumentChunk
from app.models.extracted_table import ExtractedTable
from app.models.kap_report import KapReport
from app.services.pipeline.document_parser import ParsedDocument, ParsedElement, prepend_summary_element
from app.services.pipeline.sentence_splitter import split_text_into_chunks
from app.services.utils.logging import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_TOKENS = 1024
_OVERLAP_TOKENS = 50


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PersistedContentBatch:
    created_count: int
    linked_count: int
    skipped_count: int
    markdown_path: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_stock_scoped_content_hash(stock_id: int, text: str) -> str:
    normalized = normalize_content_text(text)
    return hashlib.sha256(f"{stock_id}:{normalized}".encode("utf-8")).hexdigest()


def normalize_content_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def assemble_content_elements(
    document: ParsedDocument,
    target_tokens: int,
) -> list[ParsedElement]:
    assembled: list[ParsedElement] = []
    buffer: list[ParsedElement] = []
    buffer_tokens = 0

    def flush_buffer() -> None:
        nonlocal buffer, buffer_tokens
        if not buffer:
            return
        text = "\n\n".join(item.text for item in buffer)
        markdown = "\n\n".join(item.markdown for item in buffer)
        assembled.append(
            ParsedElement(
                element_type="paragraph_bundle" if len(buffer) > 1 else buffer[0].element_type,
                text=text,
                markdown=markdown,
                page_start=buffer[0].page_start,
                page_end=buffer[-1].page_end,
                section_path=buffer[-1].section_path,
                token_estimate=buffer_tokens,
                is_atomic=len(buffer) == 1 and buffer[0].is_atomic,
                is_summary_prefix=any(item.is_summary_prefix for item in buffer),
                content_origin=buffer[0].content_origin,
            )
        )
        buffer = []
        buffer_tokens = 0

    for element in document.elements:
        if element.is_atomic or element.token_estimate >= target_tokens:
            flush_buffer()
            assembled.append(element)
            continue

        if buffer and (
            buffer[-1].section_path != element.section_path or
            buffer_tokens + element.token_estimate > target_tokens
        ):
            flush_buffer()

        buffer.append(element)
        buffer_tokens += element.token_estimate

    flush_buffer()
    return assembled


async def _get_or_create_content(
    db: AsyncSession,
    stock_id: int,
    text: str,
    markdown: str | None,
    element_type: str,
    section_path: str | None,
    parser_version: str,
    parent_content_id: int | None,
    is_synthetic: bool,
) -> DocumentContent:
    """Fetch existing DocumentContent by hash or create a new one."""
    content_hash = build_stock_scoped_content_hash(stock_id, markdown or text)
    result = await db.execute(
        select(DocumentContent).where(
            DocumentContent.stock_id == stock_id,
            DocumentContent.content_hash == content_hash,
        )
    )
    content = result.scalar_one_or_none()

    if content is None:
        content = DocumentContent(
            stock_id=stock_id,
            content_hash=content_hash,
            content_text=text,
            content_markdown=markdown,
            processed_text=text,  # Store processed / normalized text
            content_type=element_type,
            content_origin="pdf_docling",
            section_path=section_path or None,
            is_synthetic_section=is_synthetic,
            parser_version=parser_version,
            report_occurrence_count=0,
            first_seen_report_id=None,
            last_seen_report_id=None,
            parent_content_id=parent_content_id,
            embedding_status="PENDING",
        )
        db.add(content)
        await db.flush()

    return content


async def _create_report_link(
    db: AsyncSession,
    content_id: int,
    kap_report: KapReport,
    stock_id: int,
    element_order: int,
    section_path: str | None,
    is_summary_prefix: bool,
    content_origin: str,
) -> bool:
    """Create ChunkReportLink if it does not already exist.

    Returns True if a new link was created, False if it already existed.
    """
    result = await db.execute(
        select(ChunkReportLink.id).where(
            ChunkReportLink.content_id == content_id,
            ChunkReportLink.kap_report_id == kap_report.id,
            ChunkReportLink.element_order == element_order,
        )
    )
    if result.scalar_one_or_none():
        return False

    db.add(
        ChunkReportLink(
            content_id=content_id,
            kap_report_id=kap_report.id,
            stock_id=stock_id,
            filing_type=kap_report.filing_type,
            report_section=section_path or None,
            element_order=element_order,
            is_summary_prefix=is_summary_prefix,
            content_origin=content_origin,
            published_at=kap_report.published_at,
        )
    )
    return True


async def _create_legacy_chunk(
    db: AsyncSession,
    kap_report: KapReport,
    element_order: int,
    text: str,
) -> None:
    """Create legacy DocumentChunk row if it does not already exist."""
    legacy_hash = hashlib.sha256(normalize_content_text(text).encode("utf-8")).hexdigest()
    result = await db.execute(
        select(DocumentChunk.id)
        .where(DocumentChunk.kap_report_id == kap_report.id)
        .where(DocumentChunk.chunk_text_hash == legacy_hash)
    )
    if result.scalar_one_or_none() is None:
        db.add(
            DocumentChunk(
                kap_report_id=kap_report.id,
                chunk_index=element_order,
                chunk_text=text,
                chunk_text_hash=legacy_hash,
                embedding_status="PENDING",
            )
        )


async def _persist_single_element(
    db: AsyncSession,
    kap_report: KapReport,
    stock_id: int,
    element: ParsedElement,
    element_order: int,
    parser_version: str,
    parent_content_id: int | None = None,
    is_synthetic: bool = False,
) -> DocumentContent:
    """Persist one ParsedElement to DocumentContent + ChunkReportLink + legacy chunk."""
    content = await _get_or_create_content(
        db=db,
        stock_id=stock_id,
        text=element.text,
        markdown=element.markdown,
        element_type=element.element_type,
        section_path=element.section_path or None,
        parser_version=parser_version,
        parent_content_id=parent_content_id,
        is_synthetic=is_synthetic,
    )

    # Update report occurrence tracking
    if content.first_seen_report_id is None:
        content.first_seen_report_id = kap_report.id
    if content.last_seen_report_id != kap_report.id:
        content.last_seen_report_id = kap_report.id

    await _create_report_link(
        db=db,
        content_id=content.id,
        kap_report=kap_report,
        stock_id=stock_id,
        element_order=element_order,
        section_path=element.section_path or None,
        is_summary_prefix=element.is_summary_prefix,
        content_origin=element.content_origin,
    )

    await _create_legacy_chunk(db, kap_report, element_order, element.text)

    return content


async def _persist_extracted_table(
    db: AsyncSession,
    kap_report: KapReport,
    element: ParsedElement,
) -> None:
    """Persist a table element to ExtractedTable."""
    if element.element_type != "table":
        return

    db.add(
        ExtractedTable(
            kap_report_id=kap_report.id,
            section_path=element.section_path or None,
            table_markdown=element.markdown or element.text,
            table_json=element.table_data,
            page_number=element.page_start,
        )
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


async def persist_parsed_document(
    db: AsyncSession,
    kap_report: KapReport,
    stock_id: int,
    parsed_document: ParsedDocument,
) -> PersistedContentBatch:
    settings = get_settings()
    enriched_document = prepend_summary_element(parsed_document, kap_report.summary)
    content_elements = assemble_content_elements(enriched_document, settings.chunk_target_tokens)
    markdown_path = _write_markdown_snapshot(kap_report, enriched_document.markdown)

    created_count = 0
    linked_count = 0
    skipped_count = 0
    touched_content_ids: set[int] = set()
    link_order = 0

    for element in content_elements:
        # --------------------------------------------------------------
        # 1. Extracted table persistence
        # --------------------------------------------------------------
        if element.element_type == "table" and element.table_data:
            await _persist_extracted_table(db, kap_report, element)

        # --------------------------------------------------------------
        # 2. 1024-token safety wall
        # --------------------------------------------------------------
        if element.token_estimate > _MAX_TOKENS and not element.is_atomic:
            # Create parent (not embedded)
            parent_hash = build_stock_scoped_content_hash(stock_id, element.markdown or element.text)
            parent_result = await db.execute(
                select(DocumentContent).where(
                    DocumentContent.stock_id == stock_id,
                    DocumentContent.content_hash == parent_hash,
                )
            )
            parent = parent_result.scalar_one_or_none()
            if parent is None:
                parent = DocumentContent(
                    stock_id=stock_id,
                    content_hash=parent_hash,
                    content_text=element.text,
                    content_markdown=element.markdown,
                    processed_text=element.text,
                    content_type=element.element_type,
                    content_origin=element.content_origin,
                    section_path=element.section_path or None,
                    is_synthetic_section=False,
                    parser_version=enriched_document.parser_version,
                    report_occurrence_count=0,
                    first_seen_report_id=kap_report.id,
                    last_seen_report_id=kap_report.id,
                    parent_content_id=None,
                    embedding_status="SKIPPED",  # Parent too large, do not embed
                )
                db.add(parent)
                await db.flush()
                created_count += 1
            touched_content_ids.add(parent.id)

            # Create link for parent
            parent_linked = await _create_report_link(
                db=db,
                content_id=parent.id,
                kap_report=kap_report,
                stock_id=stock_id,
                element_order=link_order,
                section_path=element.section_path or None,
                is_summary_prefix=element.is_summary_prefix,
                content_origin=element.content_origin,
            )
            if parent_linked:
                linked_count += 1
            else:
                skipped_count += 1
            link_order += 1

            # Split into child chunks
            chunks = split_text_into_chunks(
                element.text,
                max_tokens=_MAX_TOKENS,
                overlap_tokens=_OVERLAP_TOKENS,
            )
            for chunk_text in chunks:
                child_el = ParsedElement(
                    element_type="paragraph",
                    text=chunk_text,
                    markdown=chunk_text,
                    page_start=element.page_start,
                    page_end=element.page_end,
                    section_path=element.section_path,
                    token_estimate=len(chunk_text) // 4,
                    is_atomic=True,
                    content_origin=element.content_origin,
                )
                child_content = await _persist_single_element(
                    db=db,
                    kap_report=kap_report,
                    stock_id=stock_id,
                    element=child_el,
                    element_order=link_order,
                    parser_version=enriched_document.parser_version,
                    parent_content_id=parent.id,
                    is_synthetic=False,
                )
                if child_content.id not in touched_content_ids:
                    created_count += 1
                touched_content_ids.add(child_content.id)
                linked_count += 1
                link_order += 1
        else:
            content = await _persist_single_element(
                db=db,
                kap_report=kap_report,
                stock_id=stock_id,
                element=element,
                element_order=link_order,
                parser_version=enriched_document.parser_version,
                parent_content_id=None,
                is_synthetic=False,
            )
            if content.id not in touched_content_ids:
                created_count += 1
            touched_content_ids.add(content.id)
            linked_count += 1
            link_order += 1

    # --------------------------------------------------------------
    # Update occurrence counts
    # --------------------------------------------------------------
    if touched_content_ids:
        occurrence_result = await db.execute(
            select(
                ChunkReportLink.content_id,
                func.count(func.distinct(ChunkReportLink.kap_report_id)),
            )
            .where(ChunkReportLink.content_id.in_(touched_content_ids))
            .group_by(ChunkReportLink.content_id)
        )
        occurrence_map = {content_id: count for content_id, count in occurrence_result.all()}

        refreshed_contents = await db.execute(
            select(DocumentContent).where(DocumentContent.id.in_(touched_content_ids))
        )
        for content in refreshed_contents.scalars():
            content.report_occurrence_count = occurrence_map.get(content.id, 0)

    # Final report status update
    kap_report.chunk_count = linked_count + skipped_count
    kap_report.chunked_at = datetime.now(timezone.utc)
    kap_report.parser_version = enriched_document.parser_version
    kap_report.parsed_markdown_path = markdown_path
    kap_report.rag_ingest_status = "INGESTED"
    kap_report.rag_ingest_reason = "idempotent_refresh" if linked_count == 0 and skipped_count > 0 else None

    return PersistedContentBatch(
        created_count=created_count,
        linked_count=linked_count,
        skipped_count=skipped_count,
        markdown_path=markdown_path,
    )


# ---------------------------------------------------------------------------
# Markdown snapshot writer
# ---------------------------------------------------------------------------


def _write_markdown_snapshot(kap_report: KapReport, markdown: str) -> str | None:
    if not markdown.strip():
        return None

    settings = get_settings()
    if kap_report.local_pdf_path:
        relative_md_path = str(Path(kap_report.local_pdf_path).with_suffix(".md"))
    else:
        relative_md_path = f"report_{kap_report.id}.md"

    backend_root = Path(__file__).resolve().parents[3]
    markdown_base = Path(settings.parsed_markdown_storage_path)
    if not markdown_base.is_absolute():
        markdown_base = backend_root / markdown_base

    markdown_path = markdown_base / relative_md_path
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    return str(markdown_path.relative_to(backend_root)).replace("\\", "/")
