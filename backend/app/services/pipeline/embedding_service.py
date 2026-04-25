"""Embedding service for canonical RAG 2.0 document content."""

from __future__ import annotations

import chromadb
import httpx

from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chunk_report_link import ChunkReportLink
from app.models.document_content import DocumentContent
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.utils.logging import logger


OPENROUTER_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "openai/text-embedding-3-small"


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _sanitize_section_path(text: str) -> str:
    """Clean section path for use in context prepend and metadata."""
    if not text:
        return ""
    cleaned = text.replace("\n", " ").replace("\t", " ")
    cleaned = __import__("re").sub(r"\s+", " ", cleaned)
    return cleaned.strip()[:500]


def _build_embedding_text(
    content_text: str,
    stock_symbol: str,
    section_path: str | None,
    published_year: int | None,
) -> str:
    """Prepend semantic context tag before the actual chunk text."""
    symbol = stock_symbol or "N/A"
    year = str(published_year) if published_year else "N/A"
    section = _sanitize_section_path(section_path or "")
    context_tag = f"[BAĞLAM: {symbol} - {year} - {section}]"
    return f"{context_tag}\n{content_text}"

EMBEDDING_RETRY_PATTERNS = [
    "Timeout",
    "rate limit",
    "HTTP 429",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "Connection refused",
]


class EmbeddingStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EmbeddingResult(BaseModel):
    chunk_id: int
    success: bool
    chroma_document_id: str | None = None
    error_message: str | None = None
    status: EmbeddingStatus


class EmbeddingBatchResult(BaseModel):
    total_processed: int
    successful: int
    failed: int
    status: str
    results: list[EmbeddingResult] = []
    details: dict[str, Any] | None = None


_chroma_client: chromadb.ClientAPI | None = None


def _get_chroma_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        _chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return _chroma_client


def _get_or_create_collection() -> chromadb.Collection:
    settings = get_settings()
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"dimension": settings.embedding_dimension},
    )


def _is_embedding_retry_eligible(error_message: str) -> bool:
    return any(pattern.lower() in error_message.lower() for pattern in EMBEDDING_RETRY_PATTERNS)


def _build_chunk_metadata(
    chunk: Any,
    kap_report: KapReport,
    stock_symbol: str,
) -> dict[str, Any]:
    title = (kap_report.title or "")[:500]
    return {
        "stock_symbol": stock_symbol,
        "report_title": title,
        "published_at": kap_report.published_at.isoformat() if kap_report.published_at else None,
        "filing_type": kap_report.filing_type or "",
        "chunk_index": getattr(chunk, "chunk_index", 0),
        "kap_report_id": getattr(chunk, "kap_report_id", None),
        "chunk_text_hash": getattr(chunk, "chunk_text_hash", None),
    }


async def _get_embeddings_from_openrouter(
    texts: list[str],
    client: httpx.AsyncClient,
    api_key: str,
    timeout: float,
) -> list[list[float]]:
    response = await client.post(
        OPENROUTER_EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": EMBEDDING_MODEL,
            "input": texts,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()["data"]
    data.sort(key=lambda item: item["index"])
    return [item["embedding"] for item in data]


async def _build_content_metadata(
    db: AsyncSession,
    content: DocumentContent,
    stock_symbol_map: dict[int, str],
) -> dict[str, Any]:
    link_result = await db.execute(
        select(ChunkReportLink, KapReport)
        .join(KapReport, KapReport.id == ChunkReportLink.kap_report_id)
        .where(ChunkReportLink.content_id == content.id)
        .order_by(KapReport.published_at.desc())
    )
    rows = list(link_result.all())
    latest_link, latest_report = rows[0] if rows else (None, None)
    report_ids = [row.ChunkReportLink.kap_report_id for row in rows]
    published_years = sorted({row.KapReport.published_at.year for row in rows if row.KapReport.published_at})
    filing_types = sorted({row.ChunkReportLink.filing_type for row in rows if row.ChunkReportLink.filing_type})

    return {
        "content_id": content.id,
        "stock_id": content.stock_id,
        "stock_symbol": stock_symbol_map.get(content.stock_id, ""),
        "report_title": latest_report.title[:500] if latest_report and latest_report.title else "",
        "published_at": latest_report.published_at.isoformat() if latest_report and latest_report.published_at else None,
        "filing_type": latest_link.filing_type if latest_link else "",
        "source_url": latest_report.source_url if latest_report and latest_report.source_url else "",
        "kap_report_id": latest_report.id if latest_report else None,
        "latest_kap_report_id": latest_report.id if latest_report else None,
        "chunk_text_hash": content.content_hash,
        "content_hash": content.content_hash,
        "report_ids": ",".join(str(report_id) for report_id in report_ids),
        "published_years": ",".join(str(year) for year in published_years),
        "report_count": len(set(report_ids)),
        "content_type": content.content_type,
        "content_origin": content.content_origin,
        "section_path": _sanitize_section_path(content.section_path or ""),
        "evidence_mode": _derive_evidence_mode(published_years),
        "parent_content_id": content.parent_content_id,
        "is_synthetic_section": content.is_synthetic_section,
    }


def _derive_evidence_mode(published_years: list[int]) -> str:
    if len(published_years) <= 1:
        return "single_report"
    return "repeated_across_reports"


async def embed_contents_batch(
    db: AsyncSession,
    contents: list[DocumentContent],
    stock_symbol_map: dict[int, str],
) -> EmbeddingBatchResult:
    settings = get_settings()
    results: list[EmbeddingResult] = []
    successful = 0
    failed = 0

    if not contents:
        return EmbeddingBatchResult(total_processed=0, successful=0, failed=0, status="success", results=[])

    try:
        collection = _get_or_create_collection()
    except Exception as exc:
        for content in contents:
            content.embedding_status = EmbeddingStatus.FAILED.value
            results.append(
                EmbeddingResult(chunk_id=content.id, success=False, error_message=f"ChromaDB connection error: {exc}", status=EmbeddingStatus.FAILED)
            )
        await db.commit()
        return EmbeddingBatchResult(total_processed=len(contents), successful=0, failed=len(contents), status="failed", results=results)

    async with httpx.AsyncClient() as client:
        for index in range(0, len(contents), settings.embedding_batch_size):
            batch = contents[index:index + settings.embedding_batch_size]

            # Prepare metadata, ids, and embedding texts in one pass
            texts: list[str] = []
            ids: list[str] = []
            metadatas: list[dict[str, Any]] = []

            for content in batch:
                metadata = await _build_content_metadata(db, content, stock_symbol_map)
                metadatas.append(metadata)
                ids.append(content.content_hash or f"content_{content.id}")

                year_str = metadata.get("published_years", "")
                published_year = int(year_str.split(",")[-1]) if year_str else None

                embedding_text = _build_embedding_text(
                    content_text=content.content_markdown or content.content_text,
                    stock_symbol=metadata["stock_symbol"],
                    section_path=metadata["section_path"],
                    published_year=published_year,
                )
                texts.append(embedding_text)

            try:
                embeddings = await _get_embeddings_from_openrouter(
                    texts=texts,
                    client=client,
                    api_key=settings.openrouter_api_key,
                    timeout=settings.embedding_timeout,
                )
            except Exception as exc:
                error_message = str(exc)
                retry_eligible = _is_embedding_retry_eligible(error_message)
                for content in batch:
                    if retry_eligible:
                        continue
                    content.embedding_status = EmbeddingStatus.FAILED.value
                    results.append(
                        EmbeddingResult(chunk_id=content.id, success=False, error_message=error_message, status=EmbeddingStatus.FAILED)
                    )
                    failed += 1
                await db.commit()
                continue

            try:
                collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
            except Exception as exc:
                error_message = f"ChromaDB error: {exc}"
                for content in batch:
                    content.embedding_status = EmbeddingStatus.FAILED.value
                    results.append(
                        EmbeddingResult(chunk_id=content.id, success=False, error_message=error_message, status=EmbeddingStatus.FAILED)
                    )
                    failed += 1
                await db.commit()
                continue

            for content, doc_id in zip(batch, ids, strict=False):
                content.embedding_status = EmbeddingStatus.COMPLETED.value
                content.chroma_document_id = doc_id
                results.append(
                    EmbeddingResult(chunk_id=content.id, success=True, chroma_document_id=doc_id, status=EmbeddingStatus.COMPLETED)
                )
                successful += 1

            await db.commit()

    status = "success" if failed == 0 else "partial" if successful > 0 else "failed"
    return EmbeddingBatchResult(
        total_processed=len(contents),
        successful=successful,
        failed=failed,
        status=status,
        results=results,
    )


async def batch_embed_pending_chunks(
    db: AsyncSession,
    limit: int = 500,
) -> EmbeddingBatchResult:
    result = await db.execute(
        select(DocumentContent)
        .where(DocumentContent.embedding_status == EmbeddingStatus.PENDING.value)
        .order_by(DocumentContent.created_at)
        .limit(limit)
    )
    contents = list(result.scalars().all())

    if not contents:
        return EmbeddingBatchResult(total_processed=0, successful=0, failed=0, status="success", results=[])

    stock_ids = list({content.stock_id for content in contents})
    stock_symbol_map: dict[int, str] = {}
    if stock_ids:
        stocks_result = await db.execute(select(Stock.id, Stock.symbol).where(Stock.id.in_(stock_ids)))
        for stock_id, symbol in stocks_result:
            stock_symbol_map[stock_id] = symbol

    return await embed_contents_batch(db=db, contents=contents, stock_symbol_map=stock_symbol_map)


async def embed_chunks_batch(
    db: AsyncSession,
    chunks: list[Any],
    kap_report_map: dict[int, KapReport] | None = None,
    stock_symbol_map: dict[int, str] | None = None,
) -> EmbeddingBatchResult:
    if not chunks:
        return EmbeddingBatchResult(total_processed=0, successful=0, failed=0, status="success", results=[])

    if isinstance(chunks[0], DocumentContent):
        return await embed_contents_batch(db=db, contents=chunks, stock_symbol_map=stock_symbol_map or {})

    kap_report_map = kap_report_map or {}
    stock_symbol_map = stock_symbol_map or {}
    settings = get_settings()
    results: list[EmbeddingResult] = []
    successful = 0
    failed = 0
    valid_chunks: list[Any] = []
    valid_reports: list[KapReport] = []

    for chunk in chunks:
        kap_report = kap_report_map.get(getattr(chunk, "kap_report_id", None))
        if kap_report is None:
            chunk.embedding_status = EmbeddingStatus.FAILED.value
            results.append(
                EmbeddingResult(
                    chunk_id=chunk.id,
                    success=False,
                    error_message="Missing kap_report for chunk",
                    status=EmbeddingStatus.FAILED,
                )
            )
            failed += 1
            continue
        valid_chunks.append(chunk)
        valid_reports.append(kap_report)

    if not valid_chunks:
        await db.commit()
        status = "failed" if failed else "success"
        return EmbeddingBatchResult(
            total_processed=len(chunks),
            successful=successful,
            failed=failed,
            status=status,
            results=results,
        )

    try:
        collection = _get_or_create_collection()
    except Exception as exc:
        error_message = f"ChromaDB connection error: {exc}"
        for chunk in valid_chunks:
            chunk.embedding_status = EmbeddingStatus.FAILED.value
            results.append(
                EmbeddingResult(
                    chunk_id=chunk.id,
                    success=False,
                    error_message=error_message,
                    status=EmbeddingStatus.FAILED,
                )
            )
            failed += 1
        await db.commit()
        return EmbeddingBatchResult(
            total_processed=len(chunks),
            successful=successful,
            failed=failed,
            status="failed",
            results=results,
        )

    texts = [chunk.chunk_text for chunk in valid_chunks]
    async with httpx.AsyncClient() as client:
        embeddings = await _get_embeddings_from_openrouter(
            texts=texts,
            client=client,
            api_key=settings.openrouter_api_key,
            timeout=settings.embedding_timeout,
        )

    ids = [chunk.chunk_text_hash or f"chunk_{chunk.id}" for chunk in valid_chunks]
    metadatas = [
        _build_chunk_metadata(
            chunk=chunk,
            kap_report=kap_report,
            stock_symbol=stock_symbol_map.get(kap_report.stock_id, ""),
        )
        for chunk, kap_report in zip(valid_chunks, valid_reports, strict=False)
    ]
    documents = [chunk.chunk_text for chunk in valid_chunks]
    collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    for chunk, doc_id in zip(valid_chunks, ids, strict=False):
        chunk.embedding_status = EmbeddingStatus.COMPLETED.value
        chunk.chroma_document_id = doc_id
        results.append(
            EmbeddingResult(
                chunk_id=chunk.id,
                success=True,
                chroma_document_id=doc_id,
                status=EmbeddingStatus.COMPLETED,
            )
        )
        successful += 1

    await db.commit()
    status = "success" if failed == 0 else "partial" if successful > 0 else "failed"
    return EmbeddingBatchResult(
        total_processed=len(chunks),
        successful=successful,
        failed=failed,
        status=status,
        results=results,
    )
