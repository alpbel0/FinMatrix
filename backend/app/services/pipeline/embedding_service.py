"""Embedding Service for document chunks.

This service handles creating embeddings for document chunks and storing them
in ChromaDB vector database.

Key principles:
- Service functions return Pydantic result objects (no DB logging)
- Scheduler wrapper creates THE ONLY PipelineLog for the run
- Batch processing: 100 chunks per OpenRouter API call
- 500 chunks max per scheduler run
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import chromadb
import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.document_chunk import DocumentChunk
from app.models.kap_report import KapReport
from app.services.utils.logging import logger


# ============================================================================
# Constants
# ============================================================================

OPENROUTER_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "openai/text-embedding-3-small"

# Retry-eligible error patterns for embeddings
EMBEDDING_RETRY_PATTERNS = [
    "Timeout",
    "rate limit",
    "HTTP 429",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "Connection refused",
]


# ============================================================================
# Enums
# ============================================================================


class EmbeddingStatus(str, Enum):
    """Embedding status values - matches DocumentChunk.embedding_status."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ============================================================================
# Pydantic Result Models
# ============================================================================


class EmbeddingResult(BaseModel):
    """Result of embedding a single chunk."""
    chunk_id: int
    success: bool
    chroma_document_id: str | None = None
    error_message: str | None = None
    status: EmbeddingStatus


class EmbeddingBatchResult(BaseModel):
    """Result of batch embedding operation.

    NO run_id field - scheduler wrapper handles PipelineLog.
    """
    total_processed: int
    successful: int
    failed: int
    status: str  # "success", "partial", "failed"
    results: list[EmbeddingResult] = []
    details: dict[str, Any] | None = None


# ============================================================================
# ChromaDB Client (Singleton)
# ============================================================================

_chroma_client: chromadb.ClientAPI | None = None


def _get_chroma_client() -> chromadb.ClientAPI:
    """Get or create ChromaDB client (singleton pattern).

    Returns:
        ChromaDB HttpClient instance.
    """
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        _chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return _chroma_client


def _get_or_create_collection() -> chromadb.Collection:
    """Get or create the kap_documents collection.

    Returns:
        ChromaDB Collection instance.
    """
    settings = get_settings()
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"dimension": settings.embedding_dimension},
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _build_chunk_metadata(
    chunk: DocumentChunk,
    kap_report: KapReport,
    stock_symbol: str,
) -> dict[str, Any]:
    """Build metadata dict for ChromaDB document.

    Args:
        chunk: The DocumentChunk instance.
        kap_report: The parent KapReport instance.
        stock_symbol: Stock symbol string.

    Returns:
        Metadata dict with all required fields.
    """
    return {
        "stock_symbol": stock_symbol,
        "report_title": kap_report.title[:500] if kap_report.title else "",
        "published_at": kap_report.published_at.isoformat() if kap_report.published_at else None,
        "filing_type": kap_report.filing_type or "",
        "source_url": kap_report.source_url or "",
        "chunk_index": chunk.chunk_index,
        "kap_report_id": kap_report.id,
        "chunk_text_hash": chunk.chunk_text_hash or "",
    }


def _is_embedding_retry_eligible(error_message: str) -> bool:
    """Check if error is eligible for retry.

    Args:
        error_message: The error message string.

    Returns:
        True if retry-eligible, False otherwise.
    """
    return any(pattern.lower() in error_message.lower() for pattern in EMBEDDING_RETRY_PATTERNS)


async def _get_embeddings_from_openrouter(
    texts: list[str],
    client: httpx.AsyncClient,
    api_key: str,
    timeout: float,
) -> list[list[float]]:
    """Get embeddings from OpenRouter API.

    Args:
        texts: List of text strings to embed.
        client: httpx AsyncClient instance.
        api_key: OpenRouter API key.
        timeout: Request timeout in seconds.

    Returns:
        List of embedding vectors (one per text).

    Raises:
        httpx.HTTPStatusError: On API error responses.
        httpx.TimeoutException: On timeout.
    """
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
    data = response.json()

    # OpenRouter returns {"data": [{"embedding": [...], "index": 0}, ...]}
    embeddings_data = data["data"]

    # Sort by index to ensure correct order
    embeddings_data.sort(key=lambda x: x["index"])

    return [item["embedding"] for item in embeddings_data]


# ============================================================================
# Core Service Functions
# ============================================================================


async def embed_chunks_batch(
    db: AsyncSession,
    chunks: list[DocumentChunk],
    kap_report_map: dict[int, KapReport],
    stock_symbol_map: dict[int, str],
) -> EmbeddingBatchResult:
    """Embed a batch of chunks and store in ChromaDB.

    Args:
        db: AsyncSession for database operations.
        chunks: List of DocumentChunk instances to embed.
        kap_report_map: Dict mapping kap_report_id to KapReport.
        stock_symbol_map: Dict mapping stock_id to symbol.

    Returns:
        EmbeddingBatchResult with batch outcome.
    """
    settings = get_settings()
    results: list[EmbeddingResult] = []
    successful = 0
    failed = 0

    if not chunks:
        return EmbeddingBatchResult(
            total_processed=0,
            successful=0,
            failed=0,
            status="success",
            results=[],
        )

    # Get ChromaDB collection
    try:
        collection = _get_or_create_collection()
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        # Mark all chunks as failed
        for chunk in chunks:
            chunk.embedding_status = EmbeddingStatus.FAILED.value
            results.append(EmbeddingResult(
                chunk_id=chunk.id,
                success=False,
                error_message=f"ChromaDB connection error: {e}",
                status=EmbeddingStatus.FAILED,
            ))
            failed += 1
        await db.commit()

        return EmbeddingBatchResult(
            total_processed=len(chunks),
            successful=0,
            failed=failed,
            status="failed",
            results=results,
        )

    # Process in API batches of embedding_batch_size
    batch_size = settings.embedding_batch_size

    async with httpx.AsyncClient() as http_client:
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            eligible_chunks: list[DocumentChunk] = []

            for chunk in batch_chunks:
                if kap_report_map.get(chunk.kap_report_id):
                    eligible_chunks.append(chunk)
                    continue

                chunk.embedding_status = EmbeddingStatus.FAILED.value
                results.append(EmbeddingResult(
                    chunk_id=chunk.id,
                    success=False,
                    error_message=f"Missing KapReport for chunk {chunk.id}",
                    status=EmbeddingStatus.FAILED,
                ))
                failed += 1

            if not eligible_chunks:
                await db.commit()
                continue

            # Prepare texts for embedding
            texts = [chunk.chunk_text for chunk in eligible_chunks]

            # Get embeddings with retry
            embeddings: list[list[float]] | None = None
            last_error: Exception | None = None
            retry_count = 0

            while retry_count <= settings.embedding_retry_count:
                try:
                    embeddings = await _get_embeddings_from_openrouter(
                        texts=texts,
                        client=http_client,
                        api_key=settings.openrouter_api_key,
                        timeout=settings.embedding_timeout,
                    )
                    break  # Success
                except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                    last_error = e
                    error_msg = str(e)

                    if _is_embedding_retry_eligible(error_msg):
                        retry_count += 1
                        if retry_count <= settings.embedding_retry_count:
                            logger.warning(
                                f"Transient embedding error, retry {retry_count}/{settings.embedding_retry_count}: {e}"
                            )
                            await asyncio.sleep(1)  # Brief delay before retry
                    else:
                        # Non-retry error
                        break

            if embeddings is None:
                # Embedding failed for this batch
                error_message = str(last_error) if last_error else "Unknown error"
                for chunk in eligible_chunks:
                    chunk.embedding_status = EmbeddingStatus.FAILED.value
                    results.append(EmbeddingResult(
                        chunk_id=chunk.id,
                        success=False,
                        error_message=error_message,
                        status=EmbeddingStatus.FAILED,
                    ))
                    failed += 1
                await db.commit()
                continue

            # Build metadata and upsert to ChromaDB
            ids: list[str] = []
            metadatas: list[dict[str, Any]] = []
            documents: list[str] = []
            valid_chunks: list[DocumentChunk] = []

            for chunk in eligible_chunks:
                kap_report = kap_report_map[chunk.kap_report_id]
                stock_symbol = stock_symbol_map.get(kap_report.stock_id) if kap_report.stock_id else ""

                # Use chunk_text_hash as ChromaDB document ID
                doc_id = chunk.chunk_text_hash or f"chunk_{chunk.id}"

                ids.append(doc_id)
                metadatas.append(_build_chunk_metadata(chunk, kap_report, stock_symbol))
                documents.append(chunk.chunk_text)
                valid_chunks.append(chunk)

            if not valid_chunks:
                await db.commit()
                continue

            # Upsert to ChromaDB
            try:
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings[: len(valid_chunks)],  # Ensure matching length
                    metadatas=metadatas,
                    documents=documents,
                )

                # Update chunk status
                for j, chunk in enumerate(valid_chunks):
                    if j < len(embeddings):
                        chunk.embedding_status = EmbeddingStatus.COMPLETED.value
                        chunk.chroma_document_id = ids[j]
                        results.append(EmbeddingResult(
                            chunk_id=chunk.id,
                            success=True,
                            chroma_document_id=ids[j],
                            status=EmbeddingStatus.COMPLETED,
                        ))
                        successful += 1
                    else:
                        chunk.embedding_status = EmbeddingStatus.FAILED.value
                        results.append(EmbeddingResult(
                            chunk_id=chunk.id,
                            success=False,
                            error_message="Embedding index mismatch",
                            status=EmbeddingStatus.FAILED,
                        ))
                        failed += 1

            except Exception as e:
                # ChromaDB upsert error
                error_message = f"ChromaDB error: {e}"
                for chunk in eligible_chunks:
                    chunk.embedding_status = EmbeddingStatus.FAILED.value
                    results.append(EmbeddingResult(
                        chunk_id=chunk.id,
                        success=False,
                        error_message=error_message,
                        status=EmbeddingStatus.FAILED,
                    ))
                    failed += 1

            await db.commit()

    # Determine batch status
    if failed == 0:
        batch_status = "success"
    elif successful > 0:
        batch_status = "partial"
    else:
        batch_status = "failed"

    return EmbeddingBatchResult(
        total_processed=len(chunks),
        successful=successful,
        failed=failed,
        status=batch_status,
        results=results,
    )


async def batch_embed_pending_chunks(
    db: AsyncSession,
    limit: int = 500,
) -> EmbeddingBatchResult:
    """Embed all chunks that are pending embedding.

    Query DocumentChunks where embedding_status='PENDING'.
    Does NOT create PipelineLog - returns result only.

    Processing flow:
    1. Query up to `limit` chunks with embedding_status='PENDING'
    2. Load related KapReports in batch
    3. Process in API batches of embedding_batch_size (100)
    4. Return combined results

    Args:
        db: AsyncSession for database operations.
        limit: Maximum number of chunks to embed (default: 500).

    Returns:
        EmbeddingBatchResult with batch outcome.
    """
    settings = get_settings()

    # Query pending chunks
    query = (
        select(DocumentChunk)
        .where(DocumentChunk.embedding_status == EmbeddingStatus.PENDING.value)
        .order_by(DocumentChunk.created_at)
        .limit(limit)
    )

    result = await db.execute(query)
    chunks = list(result.scalars().all())

    if not chunks:
        return EmbeddingBatchResult(
            total_processed=0,
            successful=0,
            failed=0,
            status="success",
            results=[],
        )

    # Load KapReports in batch
    kap_report_ids = list(set(chunk.kap_report_id for chunk in chunks))
    kap_reports_result = await db.execute(
        select(KapReport).where(KapReport.id.in_(kap_report_ids))
    )
    kap_reports = kap_reports_result.scalars().all()
    kap_report_map = {kr.id: kr for kr in kap_reports}

    # Load stock symbols
    stock_ids = list(set(kr.stock_id for kr in kap_reports if kr.stock_id))
    stock_symbol_map: dict[int, str] = {}
    if stock_ids:
        from app.models.stock import Stock
        stocks_result = await db.execute(
            select(Stock.id, Stock.symbol).where(Stock.id.in_(stock_ids))
        )
        for row in stocks_result:
            stock_symbol_map[row[0]] = row[1]

    # Embed the chunks
    return await embed_chunks_batch(
        db=db,
        chunks=chunks,
        kap_report_map=kap_report_map,
        stock_symbol_map=stock_symbol_map,
    )
