"""Chat schemas for API request/response models.

This module contains Pydantic schemas for chat endpoints and
RAG (Retrieval-Augmented Generation) pipeline.

Key models:
- MessageRequest/MessageResponse: Basic chat message schemas
- QueryUnderstandingResult: Query analysis result
- RetrievalAgentResult: Retrieval pipeline result
- SourceItem: Source reference for RAG responses
- RAGResponse: Full RAG pipeline response
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.enums import DocumentType, QueryIntent


# ============================================================================
# Basic Chat Schemas
# ============================================================================


class MessageRequest(BaseModel):
    """Request for sending a chat message."""

    session_id: int
    message: str


class MessageResponse(BaseModel):
    """Response for a chat message (legacy, without RAG)."""

    message: str
    sources: list[dict] = []


class SessionCreateRequest(BaseModel):
    """Request for creating a new chat session."""

    title: str | None = None


class SessionResponse(BaseModel):
    """Response for a chat session."""

    id: int
    title: str | None
    created_at: datetime


# ============================================================================
# RAG Pipeline Schemas
# ============================================================================


class QueryUnderstandingResult(BaseModel):
    """Result from query understanding agent.

    Attributes:
        normalized_query: Normalized/cleaned query text
        candidate_symbol: Raw symbol extracted from query (e.g., "thy", "bim")
        document_type: Document type filter (FR, FAR, ANY)
        intent: Query intent classification
        confidence: Confidence score for the understanding
        suggested_rewrite: Optional suggested query improvement
    """

    normalized_query: str
    candidate_symbol: str | None
    document_type: DocumentType = DocumentType.ANY
    intent: QueryIntent
    confidence: float
    suggested_rewrite: str | None = None


class SourceItem(BaseModel):
    """Source reference for RAG responses.

    Used to display source information in frontend.

    Attributes:
        kap_report_id: ID of the KAP report
        stock_symbol: Stock ticker (e.g., "THYAO")
        report_title: Title of the KAP filing
        published_at: Publication date (datetime, frontend formats)
        filing_type: Type of filing (e.g., "FR")
        source_url: URL to original KAP filing
        chunk_preview: First 100 chars of the chunk
    """

    kap_report_id: int
    stock_symbol: str
    report_title: str
    published_at: datetime | None
    filing_type: str
    source_url: str
    chunk_preview: str


class RetrievalAgentResult(BaseModel):
    """Result from retrieval agent.

    Attributes:
        chunks: Retrieved document chunks
        sources: Prepared source items for display
        has_sufficient_context: Whether context is sufficient for response
        retrieval_confidence: Confidence score for retrieval quality
        context_total_chars: Total characters in all chunks
    """

    chunks: list[dict]  # RetrievedChunk-like dict
    sources: list[SourceItem]
    has_sufficient_context: bool
    retrieval_confidence: float
    context_total_chars: int


class RAGResponse(BaseModel):
    """Full RAG pipeline response.

    This is the main response type for chat messages with RAG.

    Attributes:
        answer_text: Generated answer text (Turkish)
        sources: Source references for the answer
        stock_symbol: Final resolved stock symbol
        document_type: Document type used for filtering
        confidence_note: Optional confidence note if low confidence
        insufficient_context: True if context was insufficient
    """

    answer_text: str
    sources: list[SourceItem]
    stock_symbol: str | None
    document_type: DocumentType = DocumentType.ANY
    confidence_note: str | None = None
    insufficient_context: bool = False