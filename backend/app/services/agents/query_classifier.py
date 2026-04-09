"""CrewAI-ready high-level query classifier.

The classifier decides which orchestration flow should handle a user query.
It is intentionally separate from query_understanding_agent: query
understanding extracts document intent; this module routes the whole chat flow.
"""

import json
import re
from typing import Any
from functools import lru_cache

import httpx

from app.config import get_settings
from app.schemas.chat import QueryClassificationResult
from app.schemas.enums import QueryType
from app.services.agents.crewai_adapter import create_agent_or_spec
from app.services.agents.prompt_loader import get_openrouter_chat_url, load_prompt
from app.services.agents.query_understanding_agent import _heuristic_candidate_symbol, is_greeting
from app.services.agents.symbol_resolver import HARDCODED_ALIAS_MAP
from app.services.utils.logging import logger


TEXT_TERMS = (
    "faaliyet raporu",
    "finansal rapor",
    "rapor",
    "kap",
    "açıklama",
    "aciklama",
    "risk",
    "fırsat",
    "firsat",
    "sürdürülebilirlik",
    "surdurulebilirlik",
    "yorumla",
    "ne diyor",
)
NUMERICAL_TERMS = (
    "net kar",
    "net kâr",
    "karı",
    "kârı",
    "ciro",
    "gelir",
    "roe",
    "f/k",
    "p/e",
    "borç",
    "borc",
    "özkaynak",
    "ozkaynak",
    "marj",
    "büyüme",
    "buyume",
    "oran",
)
CHART_TERMS = (
    "grafik",
    "chart",
    "çiz",
    "ciz",
    "trend",
)
COMPARISON_TERMS = (
    "karşılaştır",
    "karsilastir",
    "kıyasla",
    "kiyasla",
    "hangisi",
    "vs",
)
SYMBOL_ALIASES = set(HARDCODED_ALIAS_MAP.keys()) | set(HARDCODED_ALIAS_MAP.values())


def build_query_classifier_agent() -> Any:
    """Build the CrewAI query classifier role or fallback metadata."""
    settings = get_settings()
    return create_agent_or_spec(
        role="FinMatrix Query Classifier",
        goal="Classify a Turkish investor query into the correct FinMatrix analysis flow.",
        backstory=(
            "You are a routing specialist for a BIST-focused financial AI. "
            "You decide whether a query needs document analysis, deterministic "
            "financial metrics, comparison logic, charts, or a general response."
        ),
        llm_model=settings.query_classifier_model,
    )


@lru_cache(maxsize=1)
def get_query_classifier_agent() -> Any:
    """Return the CrewAI classifier role lazily."""
    return build_query_classifier_agent()


def _extract_symbol_candidates(query: str) -> list[str]:
    """Extract obvious symbol candidates without hitting the database."""
    candidates: list[str] = []
    query_upper = query.upper()
    tokens = re.split(r"[\s,.;:!?/\\()\[\]{}]+", query_upper)

    for token in tokens:
        normalized = token.strip()
        if not normalized:
            continue
        mapped = HARDCODED_ALIAS_MAP.get(normalized)
        symbol = mapped or normalized
        if symbol in HARDCODED_ALIAS_MAP.values() and symbol not in candidates:
            candidates.append(symbol)
        elif symbol in SYMBOL_ALIASES and symbol not in candidates:
            candidates.append(symbol)

    heuristic = _heuristic_candidate_symbol(query)
    if heuristic and (heuristic in SYMBOL_ALIASES or HARDCODED_ALIAS_MAP.get(heuristic)):
        mapped = HARDCODED_ALIAS_MAP.get(heuristic, heuristic)
        if mapped not in candidates:
            candidates.insert(0, mapped)

    return candidates


def _has_any(query_lower: str, terms: tuple[str, ...]) -> bool:
    return any(term in query_lower for term in terms)


def classify_query_heuristic(query: str) -> QueryClassificationResult:
    """Classify obvious queries with deterministic rules."""
    query_lower = query.lower()
    symbols = _extract_symbol_candidates(query)

    if is_greeting(query):
        return QueryClassificationResult(
            query_type=QueryType.GENERAL,
            symbols=[],
            confidence=0.95,
            reasoning="Simple greeting detected.",
        )

    has_comparison = (
        _has_any(query_lower, COMPARISON_TERMS)
        or len(symbols) >= 2
        or len(re.findall(r"\b[A-Z]{4,6}\b", query)) >= 2
    )
    has_numbers = _has_any(query_lower, NUMERICAL_TERMS)
    has_text = _has_any(query_lower, TEXT_TERMS)
    needs_chart = _has_any(query_lower, CHART_TERMS)

    if has_comparison:
        return QueryClassificationResult(
            query_type=QueryType.COMPARISON,
            symbols=symbols,
            needs_text_analysis=has_text or not has_numbers,
            needs_numerical_analysis=has_numbers or needs_chart,
            needs_comparison=True,
            needs_chart=needs_chart,
            confidence=0.9,
            reasoning="Comparison signal detected.",
        )

    if has_numbers:
        return QueryClassificationResult(
            query_type=QueryType.NUMERICAL_ANALYSIS,
            symbols=symbols,
            needs_text_analysis=False,
            needs_numerical_analysis=True,
            needs_chart=needs_chart,
            confidence=0.9,
            reasoning="Financial metric signal detected.",
        )

    if has_text:
        return QueryClassificationResult(
            query_type=QueryType.TEXT_ANALYSIS,
            symbols=symbols,
            needs_text_analysis=True,
            needs_chart=needs_chart,
            confidence=0.9,
            reasoning="Document/text analysis signal detected.",
        )

    return QueryClassificationResult(
        query_type=QueryType.GENERAL,
        symbols=symbols,
        confidence=0.4,
        reasoning="No strong routing signal detected.",
    )


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def _result_from_payload(payload: dict[str, Any], fallback: QueryClassificationResult) -> QueryClassificationResult:
    try:
        query_type = QueryType(payload.get("query_type", fallback.query_type.value))
    except ValueError:
        query_type = fallback.query_type

    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        symbols = fallback.symbols

    return QueryClassificationResult(
        query_type=query_type,
        symbols=[str(symbol).upper() for symbol in symbols],
        needs_text_analysis=bool(payload.get("needs_text_analysis", fallback.needs_text_analysis)),
        needs_numerical_analysis=bool(payload.get("needs_numerical_analysis", fallback.needs_numerical_analysis)),
        needs_comparison=bool(payload.get("needs_comparison", fallback.needs_comparison)),
        needs_chart=bool(payload.get("needs_chart", fallback.needs_chart)),
        confidence=float(payload.get("confidence", fallback.confidence)),
        reasoning=payload.get("reasoning") or fallback.reasoning,
    )


async def classify_query_with_llm(
    query: str,
    fallback: QueryClassificationResult,
    http_client: httpx.AsyncClient | None = None,
) -> QueryClassificationResult:
    """Classify a query via OpenRouter-compatible chat completion."""
    settings = get_settings()
    prompt_config = load_prompt("query_classifier")
    user_prompt = prompt_config.format_user_prompt(query=query)

    should_close_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=settings.llm_timeout)

    for model in (settings.query_classifier_model, settings.query_classifier_fallback_model):
        try:
            response = await client.post(
                get_openrouter_chat_url(),
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt_config.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": prompt_config.temperature,
                    "max_tokens": prompt_config.max_tokens,
                },
            )
            response.raise_for_status()
            text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            payload = _parse_json_response(text)
            if payload:
                return _result_from_payload(payload, fallback)
        except Exception as exc:
            logger.warning("Query classifier model failed: model=%s error=%s", model, exc)

    if should_close_client:
        await client.aclose()
    return fallback


async def classify_query(
    query: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> QueryClassificationResult:
    """Classify a query. Deterministic routing is preferred for obvious cases."""
    heuristic = classify_query_heuristic(query)
    if heuristic.confidence >= 0.85:
        return heuristic
    return await classify_query_with_llm(query, heuristic, http_client=http_client)
