"""Query understanding agent for extracting intent, symbol, and document type.

This agent analyzes user queries in Turkish to extract:
- Intent (SUMMARY, RISK, OPPORTUNITY, METRIC, GENERIC)
- Candidate symbol (raw input like "thy", "bim")
- Document type (FR, FAR, ANY)

Uses OpenRouter API for LLM inference with heuristic fallback.
"""

import json
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.chat import QueryUnderstandingResult
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

PROMPT_NAME = "query_understanding"
GREETING_PREFIXES = (
    "merhaba",
    "selam",
    "hey",
    "hello",
    "hi",
    "günaydın",
    "iyi akşamlar",
    "iyi geceler",
    "nasılsın",
    "naber",
)
FINANCIAL_HINTS = (
    "rapor",
    "faaliyet",
    "finansal",
    "bilanço",
    "mali tablo",
    "net kar",
    "kar",
    "ciro",
    "risk",
    "fırsat",
    "hisse",
    "kap",
    "thyao",
    "thy",
    "bim",
    "bimas",
    "asels",
    "garan",
    "akbnk",
)


# ============================================================================
# Helper Functions
# ============================================================================


def _parse_llm_response(response_text: str) -> dict[str, Any]:
    """Parse LLM response text to JSON."""
    text = response_text.strip()

    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}, text: {text[:200]}")
        return {}


def _map_intent(intent_str: str) -> QueryIntent:
    intent_map = {
        "SUMMARY": QueryIntent.SUMMARY,
        "RISK": QueryIntent.RISK,
        "OPPORTUNITY": QueryIntent.OPPORTUNITY,
        "METRIC": QueryIntent.METRIC,
        "GENERIC": QueryIntent.GENERIC,
    }
    return intent_map.get(intent_str.upper(), QueryIntent.GENERIC)


def _map_document_type(doc_type_str: str | None) -> DocumentType:
    if not doc_type_str:
        return DocumentType.ANY

    doc_map = {
        "FR": DocumentType.FR,
        "FAR": DocumentType.FAR,
        "ANY": DocumentType.ANY,
    }
    return doc_map.get(doc_type_str.upper(), DocumentType.ANY)


def _heuristic_document_type(query: str) -> DocumentType:
    query_lower = query.lower()
    if "faaliyet" in query_lower:
        return DocumentType.FAR
    if any(term in query_lower for term in ("finansal", "yıllık", "mali tablo", "bilanço", "quarterly")):
        return DocumentType.FR
    return DocumentType.ANY


def is_greeting(query: str) -> bool:
    """Check if query is a simple greeting."""
    query_lower = query.lower().strip()
    if not query_lower:
        return False
    if any(hint in query_lower for hint in FINANCIAL_HINTS):
        return False
    return any(
        query_lower == greeting or query_lower.startswith(f"{greeting} ")
        for greeting in GREETING_PREFIXES
    )


def _heuristic_intent(query: str) -> QueryIntent:
    query_lower = query.lower()
    if any(term in query_lower for term in ("risk", "tehdit", "sorun", "zarar")):
        return QueryIntent.RISK
    if any(term in query_lower for term in ("fırsat", "potansiyel", "gelecek", "büyüme")):
        return QueryIntent.OPPORTUNITY
    if any(term in query_lower for term in ("net kar", "ciro", "roe", "favök", "f/k", "pe", "borç")):
        return QueryIntent.METRIC
    if is_greeting(query):
        return QueryIntent.GENERIC
    return QueryIntent.SUMMARY


def _heuristic_candidate_symbol(query: str) -> str | None:
    query_upper = query.upper()
    for token in query_upper.replace("?", " ").replace(",", " ").split():
        normalized = token.strip()
        if 3 <= len(normalized) <= 6 and normalized.isalpha():
            return normalized
    return None


def _fallback_analysis(query: str) -> QueryUnderstandingResult:
    """Heuristic fallback when the LLM call fails or returns unusable output."""
    return QueryUnderstandingResult(
        normalized_query=query.strip(),
        candidate_symbol=_heuristic_candidate_symbol(query),
        document_type=_heuristic_document_type(query),
        intent=_heuristic_intent(query),
        confidence=0.3,
    )


# ============================================================================
# Core Agent Function
# ============================================================================


async def analyze_query(
    query: str,
    http_client: httpx.AsyncClient | None = None,
) -> QueryUnderstandingResult:
    """Analyze user query to extract intent, symbol, and document type."""
    settings = get_settings()

    try:
        prompt_config = load_prompt(PROMPT_NAME)
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {PROMPT_NAME}, using defaults")
        prompt_config = PromptConfig(model=settings.query_understanding_model)

    user_prompt = prompt_config.format_user_prompt(query=query)
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
        response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _parse_llm_response(response_text)

        if not parsed:
            logger.warning("Empty/invalid query understanding response, using heuristic fallback")
            return _fallback_analysis(query)

        result = QueryUnderstandingResult(
            normalized_query=parsed.get("normalized_query", query),
            candidate_symbol=parsed.get("candidate_symbol"),
            document_type=_map_document_type(parsed.get("document_type")),
            intent=_map_intent(parsed.get("intent", "GENERIC")),
            confidence=min(1.0, max(0.0, parsed.get("confidence", 0.5))),
            suggested_rewrite=parsed.get("suggested_rewrite"),
        )

        logger.debug(f"Query understanding result: {result}")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
        return _fallback_analysis(query)

    except Exception as e:
        logger.error(f"Query understanding error: {e}")
        return _fallback_analysis(query)

    finally:
        if should_close_client:
            await client.aclose()
