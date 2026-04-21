"""Content-centric extraction and persistence for RAG 2.0."""

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
from app.models.kap_report import KapReport
from app.services.pipeline.document_parser import ParsedDocument, ParsedElement, prepend_summary_element


@dataclass(slots=True)
class PersistedContentBatch:
    created_count: int
    linked_count: int
    skipped_count: int
    markdown_path: str | None


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
        # print(f"DEBUG: Flushing buffer with {len(buffer)} items ({buffer_tokens} tokens)")
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

    for element_order, element in enumerate(content_elements):
        content_hash = build_stock_scoped_content_hash(stock_id, element.markdown or element.text)
        content_result = await db.execute(
            select(DocumentContent).where(
                DocumentContent.stock_id == stock_id,
                DocumentContent.content_hash == content_hash,
            )
        )
        content = content_result.scalar_one_or_none()

        if content is None:
            content = DocumentContent(
                stock_id=stock_id,
                content_hash=content_hash,
                content_text=element.text,
                content_markdown=element.markdown,
                content_type=element.element_type,
                content_origin=element.content_origin,
                section_path=element.section_path or None,
                parser_version=enriched_document.parser_version,
                report_occurrence_count=0,
                first_seen_report_id=kap_report.id,
                last_seen_report_id=kap_report.id,
                embedding_status="PENDING",
            )
            db.add(content)
            await db.flush()
            created_count += 1

        touched_content_ids.add(content.id)

        link_exists = await db.execute(
            select(ChunkReportLink.id).where(
                ChunkReportLink.content_id == content.id,
                ChunkReportLink.kap_report_id == kap_report.id,
                ChunkReportLink.element_order == element_order,
            )
        )
        if link_exists.scalar_one_or_none():
            skipped_count += 1
            continue

        db.add(
            ChunkReportLink(
                content_id=content.id,
                kap_report_id=kap_report.id,
                stock_id=stock_id,
                filing_type=kap_report.filing_type,
                report_section=element.section_path or None,
                element_order=element_order,
                is_summary_prefix=element.is_summary_prefix,
                content_origin=element.content_origin,
                published_at=kap_report.published_at,
            )
        )
        linked_count += 1

        if content.last_seen_report_id != kap_report.id:
            content.last_seen_report_id = kap_report.id
        if content.first_seen_report_id is None:
            content.first_seen_report_id = kap_report.id

        legacy_hash = hashlib.sha256(normalize_content_text(element.text).encode("utf-8")).hexdigest()
        existing_legacy = await db.execute(
            select(DocumentChunk.id)
            .where(DocumentChunk.kap_report_id == kap_report.id)
            .where(DocumentChunk.chunk_text_hash == legacy_hash)
        )
        if existing_legacy.scalar_one_or_none() is None:
            db.add(
                DocumentChunk(
                    kap_report_id=kap_report.id,
                    chunk_index=element_order,
                    chunk_text=element.text,
                    chunk_text_hash=legacy_hash,
                    embedding_status="PENDING",
                )
            )

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

    # Final report status update (Idempotent success)
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
