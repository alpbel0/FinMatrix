"""Retrieval agent for fetching relevant document chunks.

This agent wraps the existing retriever service and adds:
- Post-filtering by filing type (FR/FAR)
- Multi-factor sufficiency check
- Source item preparation for frontend display

Key design: Retrieval is deterministic. LLM query rewrite is optional.
"""

from typing import Any

from app.config import get_settings
from app.schemas.chat import RetrievalAgentResult, SourceItem
from app.schemas.enums import DocumentType
from app.schemas.chat import QueryUnderstandingResult
from app.services.rag.retriever import RetrievalResult, retrieve_chunks
from app.services.utils.logging import logger


# ============================================================================
# Helper Functions
# ============================================================================


def check_sufficient_context(
    chunks: list[dict[str, Any]],
) -> tuple[bool, float, int]:
    """Check if retrieved chunks provide sufficient context.

    Multi-factor sufficiency check:
    1. At least 1 chunk (min_chunks_for_context)
    2. Best chunk distance < max_chunk_distance (L2 distance, lower is better)
    3. Total context chars >= min_total_context_chars

    Args:
        chunks: List of retrieved chunks with 'score' and 'chunk_text' fields

    Returns:
        Tuple of (has_sufficient, confidence, total_chars)
    """
    settings = get_settings()

    if not chunks:
        return False, 0.0, 0

    # Get best distance (lowest L2 distance = most similar)
    best_distance = min(c.get("score", 1.0) for c in chunks)

    # Calculate total characters
    total_chars = sum(len(c.get("chunk_text", "")) for c in chunks)

    # Calculate confidence (weighted combination)
    # Distance factor: lower distance = higher confidence
    # Length factor: more content = higher confidence
    confidence = (
        (1 - best_distance / 2.0) * 0.5 +  # Distance factor
        (min(total_chars / 2000, 1.0)) * 0.5  # Length factor
    )

    # Check all criteria
    has_sufficient = (
        len(chunks) >= settings.min_chunks_for_context and
        best_distance < settings.max_chunk_distance and  # < because lower is better
        total_chars >= settings.min_total_context_chars
    )

    return has_sufficient, confidence, total_chars


def prepare_source_items(
    chunks: list[dict[str, Any]],
) -> list[SourceItem]:
    """Prepare source items from retrieved chunks for frontend display.

    Deduplicates by kap_report_id and creates SourceItem objects.

    Args:
        chunks: List of retrieved chunks with metadata

    Returns:
        List of SourceItem objects
    """
    seen_report_ids: set[int] = set()
    sources: list[SourceItem] = []

    for chunk in chunks:
        metadata = chunk.get("metadata", {})

        kap_report_id = metadata.get("kap_report_id")
        if kap_report_id is None:
            continue

        # Deduplicate by kap_report_id
        if kap_report_id in seen_report_ids:
            continue
        seen_report_ids.add(kap_report_id)

        # Create SourceItem
        source = SourceItem(
            kap_report_id=kap_report_id,
            stock_symbol=metadata.get("stock_symbol", ""),
            report_title=metadata.get("report_title", ""),
            published_at=metadata.get("published_at"),  # Already datetime or None
            filing_type=metadata.get("filing_type", ""),
            source_url=metadata.get("source_url", ""),
            chunk_preview=chunk.get("chunk_text", "")[:100],
            report_ids=[link.get("kap_report_id") for link in metadata.get("report_links", []) if link.get("kap_report_id")],
            published_years=[year for year in metadata.get("published_years", []) if year is not None],
            consistency_count=metadata.get("consistency_count", 1),
            evidence_mode=metadata.get("evidence_mode", "single_report"),
            latest_report_id=metadata.get("latest_kap_report_id") or kap_report_id,
            evidence_note=_build_evidence_note(metadata),
        )
        sources.append(source)

    return sources


def _chunk_to_dict(chunk: Any) -> dict[str, Any]:
    """Convert RetrievedChunk or dict to dict format.

    Args:
        chunk: RetrievedChunk object or dict

    Returns:
        Dictionary representation
    """
    if isinstance(chunk, dict):
        return chunk

    # Assume it's a RetrievedChunk-like object with attributes
    return {
        "chunk_text": getattr(chunk, "chunk_text", ""),
        "score": getattr(chunk, "score", 1.0),
        "metadata": getattr(chunk, "metadata", {}),
    }


def _build_evidence_note(metadata: dict[str, Any]) -> str | None:
    years = metadata.get("published_years", [])
    if len(years) > 1:
        formatted = ", ".join(str(year) for year in years)
        return f"Bu bilgi {formatted} raporlarinda tekrar edilmistir."
    return None


# ============================================================================
# Core Agent Function
# ============================================================================


async def run_retrieval(
    query: str,
    resolved_symbol: str | None,
    document_type: DocumentType,
    understanding: QueryUnderstandingResult | None = None,
    top_k: int = 5,
    db=None,
) -> RetrievalAgentResult:
    """Run retrieval pipeline with optional query rewrite.

    Flow:
    1. Optional query rewrite (if enabled in config)
    2. Call existing retriever (deterministic)
    3. Post-filter by filing_type if document_type != ANY
    4. Sufficiency check (multi-factor)
    5. Prepare SourceItem list

    Args:
        query: Original user query
        resolved_symbol: Canonical stock symbol from resolver
        document_type: Document type filter (FR, FAR, ANY)
        understanding: Optional QueryUnderstandingResult for rewrite hints
        top_k: Number of results to retrieve

    Returns:
        RetrievalAgentResult with chunks, sources, and sufficiency info
    """
    settings = get_settings()

    # Step 1: Optional query rewrite
    retrieval_query = query
    if settings.enable_query_rewrite and understanding and understanding.suggested_rewrite:
        retrieval_query = understanding.suggested_rewrite
        logger.debug(f"Using rewritten query: {retrieval_query}")

    # Step 2: Call existing retriever
    try:
        result: RetrievalResult = await retrieve_chunks(
            query=retrieval_query,
            stock_symbol=resolved_symbol,
            top_k=top_k,
            db=db,
            filing_type=None if document_type == DocumentType.ANY else document_type.value,
        )
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        return RetrievalAgentResult(
            chunks=[],
            sources=[],
            has_sufficient_context=False,
            retrieval_confidence=0.0,
            context_total_chars=0,
        )

    # Convert to dict format
    chunks = [_chunk_to_dict(c) for c in result.chunks]

    # Step 3: Fallback filing type filter for legacy retrieval results/tests
    if document_type == DocumentType.FR:
        chunks = [c for c in chunks if c.get("metadata", {}).get("filing_type") == "FR"]
    elif document_type == DocumentType.FAR:
        chunks = [c for c in chunks if c.get("metadata", {}).get("filing_type") == "FAR"]

    # Step 4: Sufficiency check
    has_sufficient, confidence, total_chars = check_sufficient_context(chunks)

    # Step 5: Prepare sources
    sources = prepare_source_items(chunks)

    logger.debug(
        f"Retrieval result: {len(chunks)} chunks, "
        f"sufficient={has_sufficient}, confidence={confidence:.2f}"
    )

    return RetrievalAgentResult(
        chunks=chunks,
        sources=sources,
        has_sufficient_context=has_sufficient,
        retrieval_confidence=confidence,
        context_total_chars=total_chars,
    )
