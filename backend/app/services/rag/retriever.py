"""Retriever service for RAG 2.0 canonical content memory."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chunk_report_link import ChunkReportLink
from app.models.kap_report import KapReport
from app.services.pipeline.embedding_service import EMBEDDING_MODEL, OPENROUTER_EMBEDDING_URL, _get_chroma_client
from app.services.utils.logging import logger


class RetrievedChunk(BaseModel):
    chunk_text: str
    score: float
    metadata: dict[str, Any]


class RetrievalResult(BaseModel):
    query: str
    stock_symbol: str | None
    chunks: list[RetrievedChunk]
    total_results: int


async def _embed_query(
    query: str,
    client: httpx.AsyncClient,
    api_key: str,
    timeout: float,
) -> list[float]:
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
    return response.json()["data"][0]["embedding"]


def _deduplicate_results(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen_hashes: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        hash_value = chunk.metadata.get("content_hash") or chunk.metadata.get("chunk_text_hash", "")
        if not hash_value:
            seen_hashes[f"__nohash__:{id(chunk)}"] = chunk
        elif hash_value not in seen_hashes or chunk.score < seen_hashes[hash_value].score:
            seen_hashes[hash_value] = chunk
    return list(seen_hashes.values())


async def _load_report_links(db: AsyncSession, content_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    result = await db.execute(
        select(ChunkReportLink, KapReport)
        .join(KapReport, KapReport.id == ChunkReportLink.kap_report_id)
        .where(ChunkReportLink.content_id.in_(content_ids))
        .order_by(KapReport.published_at.desc())
    )

    links_by_content: dict[int, list[dict[str, Any]]] = {content_id: [] for content_id in content_ids}
    for link, report in result.all():
        links_by_content.setdefault(link.content_id, []).append(
            {
                "kap_report_id": report.id,
                "published_at": report.published_at,
                "published_year": report.published_at.year if report.published_at else None,
                "filing_type": link.filing_type,
                "source_url": report.source_url or "",
                "report_title": report.title,
                "report_section": link.report_section or "",
                "is_summary_prefix": link.is_summary_prefix,
            }
        )
    return links_by_content


async def retrieve_chunks(
    query: str,
    stock_symbol: str | None = None,
    top_k: int = 5,
    db: AsyncSession | None = None,
    filing_type: str | None = None,
) -> RetrievalResult:
    settings = get_settings()

    try:
        client = _get_chroma_client()
        collection = client.get_collection(settings.chroma_collection_name)
    except Exception as exc:
        logger.error("Failed to get ChromaDB collection: %s", exc)
        return RetrievalResult(query=query, stock_symbol=stock_symbol, chunks=[], total_results=0)

    async with httpx.AsyncClient() as http_client:
        try:
            query_embedding = await _embed_query(
                query=query,
                client=http_client,
                api_key=settings.openrouter_api_key,
                timeout=settings.embedding_timeout,
            )
        except Exception as exc:
            logger.error("Failed to embed query: %s", exc)
            return RetrievalResult(query=query, stock_symbol=stock_symbol, chunks=[], total_results=0)

    where_filter: dict[str, Any] | None = None
    if stock_symbol:
        where_filter = {"stock_symbol": {"$eq": stock_symbol.upper()}}

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("ChromaDB query error: %s", exc)
        return RetrievalResult(query=query, stock_symbol=stock_symbol, chunks=[], total_results=0)

    ids = results.get("ids", [[]])[0] or []
    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []

    chunks: list[RetrievedChunk] = []
    for index, _doc_id in enumerate(ids):
        if index >= len(documents) or index >= len(metadatas) or index >= len(distances):
            continue
        chunks.append(RetrievedChunk(chunk_text=documents[index] or "", score=distances[index], metadata=metadatas[index] or {}))

    chunks = _deduplicate_results(chunks)

    if db is not None and chunks:
        content_ids = [int(chunk.metadata.get("content_id")) for chunk in chunks if chunk.metadata.get("content_id") is not None]
        links_by_content = await _load_report_links(db, content_ids)
        enriched_chunks: list[RetrievedChunk] = []

        for chunk in chunks:
            content_id = chunk.metadata.get("content_id")
            report_links = links_by_content.get(int(content_id), []) if content_id is not None else []
            if filing_type:
                report_links = [link for link in report_links if (link.get("filing_type") or "") == filing_type]
            if filing_type and not report_links:
                continue

            published_years = [link["published_year"] for link in report_links if link.get("published_year") is not None]
            chunk.metadata["report_links"] = report_links
            chunk.metadata["published_years"] = published_years
            chunk.metadata["consistency_count"] = len({link["kap_report_id"] for link in report_links})
            chunk.metadata["evidence_mode"] = "repeated_across_reports" if len(set(published_years)) > 1 else "single_report"
            if report_links:
                chunk.metadata["kap_report_id"] = report_links[0]["kap_report_id"]
                chunk.metadata["source_url"] = report_links[0]["source_url"]
                chunk.metadata["report_title"] = report_links[0]["report_title"]
                chunk.metadata["filing_type"] = report_links[0]["filing_type"]
                chunk.metadata["published_at"] = report_links[0]["published_at"].isoformat() if report_links[0]["published_at"] else None
            enriched_chunks.append(chunk)

        chunks = enriched_chunks

    chunks.sort(key=lambda item: item.score)
    chunks = chunks[:top_k]
    return RetrievalResult(query=query, stock_symbol=stock_symbol, chunks=chunks, total_results=len(chunks))
