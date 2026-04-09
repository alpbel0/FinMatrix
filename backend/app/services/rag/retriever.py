"""Retriever service for RAG queries.

This service handles retrieving relevant document chunks from ChromaDB
based on user queries.

Key features:
- Query embedding via OpenRouter
- ChromaDB similarity search with L2 distance
- Metadata filtering (stock symbol)
- Deduplication by chunk_text_hash
"""

from typing import Any

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.services.pipeline.embedding_service import (
    EMBEDDING_MODEL,
    OPENROUTER_EMBEDDING_URL,
    _get_chroma_client,
)
from app.services.utils.logging import logger


# ============================================================================
# Pydantic Models
# ============================================================================


class RetrievedChunk(BaseModel):
    """A retrieved chunk with source info."""
    chunk_text: str
    score: float  # L2 distance (lower = more similar)
    metadata: dict[str, Any]  # stock_symbol, report_title, published_at, filing_type, chunk_index, kap_report_id


class RetrievalResult(BaseModel):
    """Result of a retrieval query."""
    query: str
    stock_symbol: str | None
    chunks: list[RetrievedChunk]
    total_results: int


# ============================================================================
# Helper Functions
# ============================================================================


async def _embed_query(
    query: str,
    client: httpx.AsyncClient,
    api_key: str,
    timeout: float,
) -> list[float]:
    """Embed a single query string.

    Args:
        query: The query text.
        client: httpx AsyncClient instance.
        api_key: OpenRouter API key.
        timeout: Request timeout in seconds.

    Returns:
        Embedding vector.

    Raises:
        httpx.HTTPStatusError: On API error.
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
            "input": [query],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()

    # OpenRouter returns {"data": [{"embedding": [...], "index": 0}]}
    return data["data"][0]["embedding"]


def _deduplicate_results(
    chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Deduplicate results by chunk_text_hash.

    If same hash appears multiple times, keep the one with lowest score (most similar).

    Args:
        chunks: List of retrieved chunks.

    Returns:
        Deduplicated list of chunks.
    """
    seen_hashes: dict[str, RetrievedChunk] = {}

    for chunk in chunks:
        hash_value = chunk.metadata.get("chunk_text_hash", "")
        if not hash_value:
            # No hash available: do not collapse unrelated results into one bucket.
            seen_hashes[f"__nohash__:{id(chunk)}"] = chunk
        elif hash_value not in seen_hashes:
            seen_hashes[hash_value] = chunk
        elif chunk.score < seen_hashes[hash_value].score:
            # Keep the one with lower score (more similar)
            seen_hashes[hash_value] = chunk

    return list(seen_hashes.values())


# ============================================================================
# Core Service Functions
# ============================================================================


async def retrieve_chunks(
    query: str,
    stock_symbol: str | None = None,
    top_k: int = 5,
) -> RetrievalResult:
    """Retrieve relevant chunks from ChromaDB.

    Args:
        query: User query text (Turkish).
        stock_symbol: Optional filter for specific stock (e.g., "THYAO").
        top_k: Number of results (default: 5).

    Returns:
        RetrievalResult with chunks sorted by relevance (lowest L2 distance first).
    """
    settings = get_settings()

    # Get ChromaDB collection
    try:
        client = _get_chroma_client()
        collection = client.get_collection(settings.chroma_collection_name)
    except Exception as e:
        logger.error(f"Failed to get ChromaDB collection: {e}")
        return RetrievalResult(
            query=query,
            stock_symbol=stock_symbol,
            chunks=[],
            total_results=0,
        )

    # Embed query
    query_embedding: list[float] | None = None

    async with httpx.AsyncClient() as http_client:
        try:
            query_embedding = await _embed_query(
                query=query,
                client=http_client,
                api_key=settings.openrouter_api_key,
                timeout=settings.embedding_timeout,
            )
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return RetrievalResult(
                query=query,
                stock_symbol=stock_symbol,
                chunks=[],
                total_results=0,
            )

    if not query_embedding:
        return RetrievalResult(
            query=query,
            stock_symbol=stock_symbol,
            chunks=[],
            total_results=0,
        )

    # Build metadata filter
    where_filter: dict[str, Any] | None = None
    if stock_symbol:
        where_filter = {"stock_symbol": {"$eq": stock_symbol.upper()}}

    # Query ChromaDB
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,  # Fetch more for dedup
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"ChromaDB query error: {e}")
        return RetrievalResult(
            query=query,
            stock_symbol=stock_symbol,
            chunks=[],
            total_results=0,
        )

    # Parse results
    chunks: list[RetrievedChunk] = []

    if not results["ids"] or not results["ids"][0]:
        return RetrievalResult(
            query=query,
            stock_symbol=stock_symbol,
            chunks=[],
            total_results=0,
        )

    ids = results["ids"][0]
    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []

    for i, doc_id in enumerate(ids):
        if i >= len(documents) or i >= len(metadatas) or i >= len(distances):
            continue

        chunk = RetrievedChunk(
            chunk_text=documents[i] or "",
            score=distances[i],
            metadata=metadatas[i] or {},
        )
        chunks.append(chunk)

    # Deduplicate
    chunks = _deduplicate_results(chunks)

    # Limit to top_k
    chunks = chunks[:top_k]

    # Sort by score (lowest first = most similar)
    chunks.sort(key=lambda x: x.score)

    return RetrievalResult(
        query=query,
        stock_symbol=stock_symbol,
        chunks=chunks,
        total_results=len(chunks),
    )
