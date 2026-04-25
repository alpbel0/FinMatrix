"""Triage service for RAG document ingestion.

Filters parsed PDF elements through a three-tier system:
1. Blacklist (regex) -> immediate DISCARD
2. Whitelist (regex) -> immediate KEEP
3. Greylist -> LLM check (4o-mini) for unknown / None section paths

Also handles the None Section Path flow where Docling fails to assign
a section_path to a block.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.processing_cache import ProcessingCache
from app.services.agents.prompt_loader import get_openrouter_chat_url
from app.services.pipeline.document_parser import ParsedElement
from app.services.utils.logging import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Blacklist: sections with zero analytical value
_BLACKLIST_PATTERNS = [
    re.compile(r"ba[gğ][ıi]ms[ıi]z\s*denet[cç]i", re.IGNORECASE),
    re.compile(r"sorumluluk\s*beyan[ıi]", re.IGNORECASE),
    re.compile(r"kapak\s*sayfa[sf]", re.IGNORECASE),
    re.compile(r"[iİ]çindekiler", re.IGNORECASE),
    re.compile(r"\btoc\b", re.IGNORECASE),
    re.compile(r"içerik\s*listesi", re.IGNORECASE),
    re.compile(r"contents", re.IGNORECASE),
    re.compile(r"index\s*of\s*contents", re.IGNORECASE),
    re.compile(r"yeminli\s*mali\s*m[uü]şavir", re.IGNORECASE),
    re.compile(r"denetim\s*kurulu", re.IGNORECASE),
    re.compile(r"genel\s*kurul\s*[iİ]lan[ıi]", re.IGNORECASE),
    re.compile(r"[ıi]mza\s*sayfa[sf]", re.IGNORECASE),
    re.compile(r"signature\s*page", re.IGNORECASE),
]

# Whitelist: sections with definite analytical value
_WHITELIST_PATTERNS = [
    re.compile(r"bilanço", re.IGNORECASE),
    re.compile(r"gelir\s*tablosu", re.IGNORECASE),
    re.compile(r"nakit\s*ak[ıi][sş]\s*tablosu", re.IGNORECASE),
    re.compile(r"y[oö]netim\s*kurulu?\s*raporu", re.IGNORECASE),
    re.compile(r"[oö]nemli\s*olay", re.IGNORECASE),
    re.compile(r"finansal\s*durum", re.IGNORECASE),
    re.compile(r"faaliyet\s*sonu[çc]lar[ıi]", re.IGNORECASE),
    re.compile(r"sermaye\s*yap[ıi]s[ıi]", re.IGNORECASE),
    re.compile(r"risk\s*y[oö]netimi", re.IGNORECASE),
    re.compile(r"i[cç]sel\s*y[oö]netmelik", re.IGNORECASE),
    re.compile(r"kurumsal\s*y[oö]netim", re.IGNORECASE),
    re.compile(r"s[uü]rd[uü]r[uü]lebilirlik", re.IGNORECASE),
    re.compile(r"pay\s*ba[gğ][ıi][sş][ıi]", re.IGNORECASE),
    re.compile(r"[oö]zsermaye\s*harcama", re.IGNORECASE),
    re.compile(r"varl[ıi]k\s*yap[ıi]s[ıi]", re.IGNORECASE),
]

_BATCH_SIZE = 25  # 20-30 sweet spot for attention
_MAX_LLM_TRIAGE_TOKENS = 512


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TriageDecision(str, Enum):
    KEEP = "KEEP"
    DISCARD = "DISCARD"
    SYNTHETIC = "SYNTHETIC"
    REVIEW = "REVIEW"


@dataclass(slots=True)
class TriageResult:
    decision: TriageDecision
    suggested_section: str | None = None
    reason: str = ""


@dataclass(slots=True)
class TriageItem:
    element: ParsedElement
    section_path: str | None
    text_preview: str
    element_type: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def filter_elements(
    elements: list[ParsedElement],
    db: AsyncSession,
    stock_symbol: str = "",
    report_year: int = 0,
) -> list[tuple[ParsedElement, TriageResult]]:
    """Run the full triage pipeline over parsed elements.

    Returns a list of (element, result) tuples for elements that are
    KEEP or SYNTHETIC.  DISCARD elements are omitted.
    """
    kept: list[tuple[ParsedElement, TriageResult]] = []

    # Phase 1: deterministic filters (no DB/LLM needed)
    greylist_items: list[TriageItem] = []
    for element in elements:
        result = _deterministic_triage(element)
        if result.decision == TriageDecision.DISCARD:
            continue
        if result.decision == TriageDecision.KEEP:
            kept.append((element, result))
            continue
        if result.decision == TriageDecision.REVIEW:
            # Greylist -> needs LLM or cache
            greylist_items.append(
            TriageItem(
                element=element,
                section_path=element.section_path or None,
                text_preview=_make_text_preview(element.text),
                element_type=element.element_type,
            )
        )

    if not greylist_items:
        return kept

    # Phase 2: cache lookup + LLM batch processing
    cache_results = await _resolve_via_cache_and_llm(
        greylist_items,
        db,
        stock_symbol=stock_symbol,
        report_year=report_year,
    )

    for item, result in zip(greylist_items, cache_results):
        if result.decision == TriageDecision.DISCARD:
            continue
        if result.decision == TriageDecision.SYNTHETIC and result.suggested_section:
            # Mutate element in-place with synthetic section
            item.element.section_path = result.suggested_section
            item.element.is_synthetic = True
        kept.append((item.element, result))

    return kept


# ---------------------------------------------------------------------------
# Deterministic triage
# ---------------------------------------------------------------------------


def _deterministic_triage(element: ParsedElement) -> TriageResult:
    section = (element.section_path or "").strip()

    # 1. Blacklist
    if _matches_any(section, _BLACKLIST_PATTERNS):
        return TriageResult(
            decision=TriageDecision.DISCARD,
            reason="blacklist_match",
        )

    # 2. Whitelist
    if _matches_any(section, _WHITELIST_PATTERNS):
        return TriageResult(
            decision=TriageDecision.KEEP,
            reason="whitelist_match",
        )

    # 3. Quick discard: very short and no letters
    text = element.text.strip()
    if len(text) < 20 and not any(c.isalpha() for c in text):
        return TriageResult(
            decision=TriageDecision.DISCARD,
            reason="greylist_too_short_no_alpha",
        )

    # Needs further review
    return TriageResult(
        decision=TriageDecision.REVIEW,
        reason="greylist",
    )


def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in patterns)


def _normalize_section_path(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().lower()


def _make_text_preview(text: str, max_chars: int = 400) -> str:
    """Build a preview of ~100 tokens (≈400 chars) for LLM context."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    # Try to break at sentence boundary
    trunc = cleaned[:max_chars]
    last_period = trunc.rfind(".")
    if last_period > max_chars * 0.5:
        return trunc[: last_period + 1]
    return trunc + " ..."


# ---------------------------------------------------------------------------
# Cache + LLM resolution
# ---------------------------------------------------------------------------


async def _resolve_via_cache_and_llm(
    items: list[TriageItem],
    db: AsyncSession,
    stock_symbol: str,
    report_year: int,
) -> list[TriageResult]:
    """Resolve greylist items using cache first, then batched LLM calls."""
    results: list[TriageResult | None] = [None] * len(items)
    pending_indices: list[int] = []
    pending_keys: list[str] = []

    # 1. Cache lookup
    for idx, item in enumerate(items):
        cache_key = _normalize_section_path(item.section_path)
        if not cache_key:
            # None section path items always go to LLM
            pending_indices.append(idx)
            pending_keys.append("")
            continue

        cache_entry = await _get_cache_entry(db, cache_key)
        if cache_entry:
            decision = TriageDecision(cache_entry.decision)
            suggested = cache_entry.suggested_label if decision == TriageDecision.SYNTHETIC else None
            results[idx] = TriageResult(
                decision=decision,
                suggested_section=suggested,
                reason="cache_hit",
            )
        else:
            pending_indices.append(idx)
            pending_keys.append(cache_key)

    # 2. Batch LLM calls for uncached items
    if pending_indices:
        llm_results = await _batch_llm_triage(
            [items[i] for i in pending_indices],
            stock_symbol=stock_symbol,
            report_year=report_year,
        )
        # Write cache for each LLM result
        for list_idx, llm_result in zip(pending_indices, llm_results):
            results[list_idx] = llm_result
            cache_key = _normalize_section_path(items[list_idx].section_path)
            await _write_cache_entry(
                db,
                cache_key=cache_key or f"__none__:{hash(items[list_idx].text_preview) & 0xFFFFFF}",
                result=llm_result,
            )

    return [r for r in results if r is not None]


async def _get_cache_entry(
    db: AsyncSession,
    cache_key: str,
) -> ProcessingCache | None:
    result = await db.execute(
        select(ProcessingCache).where(
            ProcessingCache.section_path == cache_key,
        )
    )
    return result.scalar_one_or_none()


async def _write_cache_entry(
    db: AsyncSession,
    cache_key: str,
    result: TriageResult,
) -> None:
    existing = await _get_cache_entry(db, cache_key)
    if existing:
        existing.decision = result.decision.value
        existing.suggested_label = result.suggested_section
        existing.decided_by = "triage_llm"
        return

    db.add(
        ProcessingCache(
            section_path=cache_key,
            decision=result.decision.value,
            suggested_label=result.suggested_section,
            decided_by="triage_llm",
        )
    )


# ---------------------------------------------------------------------------
# LLM Triage
# ---------------------------------------------------------------------------


async def _batch_llm_triage(
    items: list[TriageItem],
    stock_symbol: str,
    report_year: int,
) -> list[TriageResult]:
    """Send items to 4o-mini in batches and return decisions."""
    if not items:
        return []

    settings = get_settings()
    api_key = settings.openrouter_api_key
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set; defaulting all greylist items to KEEP")
        return [
            TriageResult(decision=TriageDecision.KEEP, reason="no_api_key_fallback")
            for _ in items
        ]

    all_results: list[TriageResult] = []
    for i in range(0, len(items), _BATCH_SIZE):
        batch = items[i : i + _BATCH_SIZE]
        batch_results = await _single_llm_call(
            batch,
            api_key=api_key,
            stock_symbol=stock_symbol,
            report_year=report_year,
        )
        all_results.extend(batch_results)

    return all_results


async def _single_llm_call(
    items: list[TriageItem],
    api_key: str,
    stock_symbol: str,
    report_year: int,
) -> list[TriageResult]:
    """Call 4o-mini for a single batch of triage items."""
    settings = get_settings()
    prompt = _build_triage_prompt(items, stock_symbol, report_year)

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            response = await client.post(
                get_openrouter_chat_url(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a financial document triage assistant. "
                                "Your job is to decide whether each block from a Turkish "
                                "KAP (Public Disclosure Platform) financial report is valuable "
                                "for investment analysis. Respond ONLY with valid JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": _MAX_LLM_TRIAGE_TOKENS,
                },
            )
            response.raise_for_status()
            text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return _parse_llm_response(text, len(items))
    except Exception as exc:
        logger.warning("Triage LLM call failed: %s", exc)
        # Fallback: keep all items
        return [
            TriageResult(decision=TriageDecision.KEEP, reason="llm_error_fallback")
            for _ in items
        ]


def _build_triage_prompt(
    items: list[TriageItem],
    stock_symbol: str,
    report_year: int,
) -> str:
    """Build the user prompt for the triage LLM.

    Each item includes element_type so the LLM knows if a block is a table,
    heading, or paragraph — tables are more likely to be valuable.
    """
    lines: list[str] = [
        f"Triage blocks from {stock_symbol} {report_year} KAP financial report.",
        "",
        "For each block, decide if it is valuable for investment analysis.",
        "Respond with a JSON array where each element is:",
        '{"is_valuable": true/false, "suggested_section": "string or null"}',
        "",
        "Rules:",
        "- If section_path is empty/null (None), examine the text and suggest a section name if valuable.",
        "- suggested_section should be in Turkish, concise (max 5 words), and descriptive.",
        "- Tables (element_type=table) are generally valuable unless they are purely decorative.",
        "- Headings (element_type=heading) are valuable if they introduce a substantive section.",
        "- Paragraphs with specific financial data, forward guidance, or risk disclosures are valuable.",
        "- Boilerplate, legal disclaimers, and repeating TOC entries are NOT valuable.",
        "",
        "Blocks:",
    ]

    for idx, item in enumerate(items, 1):
        section = item.section_path or "(None)"
        lines.append(f"\n{idx}. Section: {section}")
        lines.append(f"   Type: {item.element_type}")
        lines.append(f"   Text: {item.text_preview}")

    lines.append("\nJSON response:")
    return "\n".join(lines)


def _parse_llm_response(text: str, expected_count: int) -> list[TriageResult]:
    """Parse the LLM JSON response into TriageResult objects."""
    try:
        cleaned = text.strip()
        # Extract JSON array if wrapped in markdown
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        if not isinstance(data, list):
            data = [data]

        results: list[TriageResult] = []
        for item in data[:expected_count]:
            is_valuable = bool(item.get("is_valuable", True))
            suggested = item.get("suggested_section")
            if isinstance(suggested, str):
                suggested = suggested.strip() or None
            else:
                suggested = None

            if is_valuable:
                if suggested:
                    results.append(
                        TriageResult(
                            decision=TriageDecision.SYNTHETIC,
                            suggested_section=suggested,
                            reason="llm_synthetic",
                        )
                    )
                else:
                    results.append(
                        TriageResult(
                            decision=TriageDecision.KEEP,
                            reason="llm_keep",
                        )
                    )
            else:
                results.append(
                    TriageResult(
                        decision=TriageDecision.DISCARD,
                        reason="llm_discard",
                    )
                )

        # Pad if LLM returned fewer items than expected
        while len(results) < expected_count:
            results.append(
                TriageResult(decision=TriageDecision.KEEP, reason="llm_undercount_fallback")
            )

        return results

    except Exception as exc:
        logger.warning("Failed to parse triage LLM response: %s", exc)
        return [
            TriageResult(decision=TriageDecision.KEEP, reason="parse_error_fallback")
            for _ in range(expected_count)
        ]
