"""Response agent for generating Turkish answers with source citations.

This agent generates the final response to user queries based on:
- Original user query (not normalized)
- Query understanding result
- Retrieval result with chunks and sources

Key features:
- Turkish language output
- Source citation mandatory
- No hallucination (only use retrieved content)
- Soft fallback for insufficient context
"""

from typing import Any

import httpx

from app.config import get_settings
from app.schemas.chat import QueryUnderstandingResult, RAGResponse, RetrievalAgentResult, SourceItem
from app.schemas.enums import DocumentType, QueryIntent
from app.services.agents.prompt_loader import (
    PromptConfig,
    get_openrouter_chat_url,
    load_prompt,
)
from app.services.utils.logging import logger


# ============================================================================
# Constants
# ============================================================================

PROMPT_NAME = "response_agent"

# Fallback response for insufficient context
INSUFFICIENT_CONTEXT_RESPONSE = (
    "Bu konuda elimizde yeterli bilgi bulunmuyor. "
    "Daha spesifik bir soru veya farklı bir hisse deneyebilirsiniz."
)

# Greeting response
GREETING_RESPONSE = (
    "Merhaba! BIST hisse senedi raporları hakkında sorularınızı yanıtlamaya hazırım. "
    "Örnek: 'THYAO faaliyet raporu ne diyor?' veya 'GARAN riskleri neler?'"
)


# ============================================================================
# Helper Functions
# ============================================================================


def _format_context_chunks(chunks: list[dict[str, Any]]) -> str:
    """Format chunks for LLM context.

    Args:
        chunks: List of retrieved chunks

    Returns:
        Formatted context string
    """
    if not chunks:
        return "KAYNAK BULUNAMADI"

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("chunk_text", "")
        metadata = chunk.get("metadata", {})
        symbol = metadata.get("stock_symbol", "?")
        title = metadata.get("report_title", "?")
        filing_type = metadata.get("filing_type", "?")

        formatted.append(
            f"[Kaynak {i}] {symbol} - {title} ({filing_type})\n"
            f"{text[:500]}..."  # Truncate long chunks
        )

    return "\n\n".join(formatted)


# ============================================================================
# Core Agent Function
# ============================================================================


async def generate_response(
    original_query: str,
    understanding: QueryUnderstandingResult,
    retrieval: RetrievalAgentResult,
    memory_context: str = "",
    structured_financial_context: str = "",
    http_client: httpx.AsyncClient | None = None,
) -> RAGResponse:
    """Generate RAG response with source citations.

    Args:
        original_query: Original user query (not normalized)
        understanding: Query understanding result
        retrieval: Retrieval result with chunks and sources
        memory_context: Recent chat history formatted as text
        structured_financial_context: Verified metrics loaded from structured DB
        http_client: Optional httpx AsyncClient

    Returns:
        RAGResponse with answer text and sources
    """
    settings = get_settings()

    # Handle GENERIC intent (greeting)
    if understanding.intent == QueryIntent.GENERIC:
        return RAGResponse(
            answer_text=GREETING_RESPONSE,
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            confidence_note="Sistem belge odaklı çalışmaktadır.",
            insufficient_context=False,
        )

    # Handle insufficient context
    if not retrieval.has_sufficient_context:
        return RAGResponse(
            answer_text=INSUFFICIENT_CONTEXT_RESPONSE,
            sources=retrieval.sources,  # Still show what we found
            stock_symbol=None,
            document_type=understanding.document_type,
            confidence_note=f"Güven skoru: {retrieval.retrieval_confidence:.2f}",
            insufficient_context=True,
        )

    # Load prompt
    try:
        prompt_config = load_prompt(PROMPT_NAME)
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {PROMPT_NAME}, using defaults")
        prompt_config = PromptConfig(model=settings.response_agent_model)

    # Format context
    context_text = _format_context_chunks(retrieval.chunks)

    # Format user prompt
    user_prompt = prompt_config.format_user_prompt(
        original_query=original_query,
        symbol=understanding.candidate_symbol or "belirtilmemiş",
        document_type=understanding.document_type.value,
        intent=understanding.intent.value,
        memory_context=memory_context or "Önceki konuşma yok.",
        structured_financial_context=structured_financial_context or "YAPILANDIRILMIS FINANSAL VERI YOK.",
        context_chunks=context_text,
        insufficient_context="hayır" if retrieval.has_sufficient_context else "evet",
        confidence=f"{retrieval.retrieval_confidence:.2f}",
    )

    # Build request
    messages = [
        {"role": "system", "content": prompt_config.system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    request_body = {
        "model": prompt_config.model,
        "messages": messages,
        "temperature": prompt_config.temperature,
        "max_tokens": prompt_config.max_tokens,
    }

    # Make API call
    should_close_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=settings.llm_timeout)

    try:
        response = await client.post(
            get_openrouter_chat_url(),
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
        )
        response.raise_for_status()

        data = response.json()
        answer_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Build confidence note
        confidence_note = None
        if retrieval.retrieval_confidence < 0.5:
            confidence_note = "Not: Bu yanıt düşük güven skoru ile üretilmiştir."

        return RAGResponse(
            answer_text=answer_text,
            sources=retrieval.sources,
            stock_symbol=understanding.candidate_symbol,  # Will be resolved symbol in service
            document_type=understanding.document_type,
            confidence_note=confidence_note,
            insufficient_context=False,
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
        return RAGResponse(
            answer_text="Yanıt üretilirken bir hata oluştu. Lütfen tekrar deneyin.",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            confidence_note=f"API hatası: {e.response.status_code}",
            insufficient_context=True,
        )

    except Exception as e:
        logger.error(f"Response generation error: {e}")
        return RAGResponse(
            answer_text="Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            confidence_note=f"Hata: {str(e)[:100]}",
            insufficient_context=True,
        )

    finally:
        if should_close_client:
            await client.aclose()
