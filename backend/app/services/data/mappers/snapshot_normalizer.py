"""Normalization helpers for raw snapshot payloads."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.services.data.provider_models import StockSnapshot
from app.services.data.providers.snapshot_provider import RawSnapshotPayload


SNAPSHOT_FIELDS = [
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "trailing_eps",
    "roe",
    "roa",
    "current_ratio",
    "debt_equity",
    "revenue_growth",
    "net_profit_growth",
    "foreign_ratio",
    "free_float",
    "year_high",
    "year_low",
    "ma_50",
    "ma_200",
    "market_cap",
    "last_price",
    "daily_volume",
]

PERCENTAGE_FIELDS = {
    "dividend_yield",
    "roe",
    "roa",
    "foreign_ratio",
    "free_float",
    "revenue_growth",
    "net_profit_growth",
}


def normalize_snapshot_payload(
    primary_snapshot: RawSnapshotPayload | StockSnapshot | None,
    supplements: list[RawSnapshotPayload] | None = None,
) -> dict:
    """Normalize provider-shaped snapshot payloads into DB-ready values."""
    raw_primary = _coerce_raw_payload(primary_snapshot)
    raw_supplements = supplements or []

    payload, field_sources = _build_normalized_values(raw_primary, raw_supplements)
    payload["source"] = "+".join(dict.fromkeys(field_sources.values())) or "unknown"
    payload["field_sources"] = field_sources
    payload["fetched_at"] = _latest_fetched_at(raw_primary, raw_supplements)
    return payload


def finalize_snapshot_payload(
    payload: dict[str, Any],
    field_sources: dict[str, str],
) -> dict[str, Any]:
    """Attach completeness metadata after precedence resolution."""
    missing_fields_count = sum(1 for field in SNAPSHOT_FIELDS if payload.get(field) is None)
    completeness_score = round((len(SNAPSHOT_FIELDS) - missing_fields_count) / len(SNAPSHOT_FIELDS), 4)
    critical_missing = [
        field
        for field in ("last_price", "market_cap", "pe_ratio", "pb_ratio")
        if payload.get(field) is None
    ]

    payload["field_sources"] = field_sources
    payload["source"] = "+".join(dict.fromkeys(field_sources.values())) or "unknown"
    payload["missing_fields_count"] = missing_fields_count
    payload["completeness_score"] = completeness_score
    payload["is_partial"] = bool(critical_missing or missing_fields_count > 0)
    return payload


def _build_normalized_values(
    raw_primary: RawSnapshotPayload | None,
    raw_supplements: list[RawSnapshotPayload],
) -> tuple[dict[str, Any], dict[str, str]]:
    fast_info = raw_primary.get_section("fast_info") if raw_primary else {}
    info = raw_primary.get_section("info") if raw_primary else {}
    canonical = raw_primary.get_section("canonical") if raw_primary else {}
    supplement = _merge_sections(raw_supplements, "supplement")

    payload: dict[str, Any] = {
        "pe_ratio": _pick_numeric(
            "pe_ratio",
            [
                (fast_info.get("pe_ratio"), _provider_source(raw_primary)),
                (info.get("pe_ratio"), _provider_source(raw_primary)),
                (info.get("trailingPE"), _provider_source(raw_primary)),
                (canonical.get("pe_ratio"), _provider_source(raw_primary)),
            ],
        ),
        "pb_ratio": _pick_numeric(
            "pb_ratio",
            [
                (fast_info.get("pb_ratio"), _provider_source(raw_primary)),
                (info.get("pb_ratio"), _provider_source(raw_primary)),
                (info.get("priceToBook"), _provider_source(raw_primary)),
                (canonical.get("pb_ratio"), _provider_source(raw_primary)),
            ],
        ),
        "dividend_yield": _pick_numeric(
            "dividend_yield",
            [
                (info.get("dividend_yield"), _provider_source(raw_primary)),
                (info.get("dividendYield"), _provider_source(raw_primary)),
                (canonical.get("dividend_yield"), _provider_source(raw_primary)),
            ],
            is_percentage=True,
        ),
        "trailing_eps": _pick_numeric(
            "trailing_eps",
            [
                (info.get("trailing_eps"), _provider_source(raw_primary)),
                (info.get("trailingEps"), _provider_source(raw_primary)),
                (info.get("eps"), _provider_source(raw_primary)),
                (canonical.get("trailing_eps"), _provider_source(raw_primary)),
            ],
        ),
        "roe": _pick_numeric(
            "roe",
            [
                (info.get("roe"), _provider_source(raw_primary)),
                (info.get("returnOnEquity"), _provider_source(raw_primary)),
                (canonical.get("roe"), _provider_source(raw_primary)),
            ],
            is_percentage=True,
        ),
        "roa": _pick_numeric(
            "roa",
            [
                (info.get("roa"), _provider_source(raw_primary)),
                (info.get("returnOnAssets"), _provider_source(raw_primary)),
                (canonical.get("roa"), _provider_source(raw_primary)),
            ],
            is_percentage=True,
        ),
        "current_ratio": _pick_numeric(
            "current_ratio",
            [
                (info.get("current_ratio"), _provider_source(raw_primary)),
                (info.get("currentRatio"), _provider_source(raw_primary)),
                (canonical.get("current_ratio"), _provider_source(raw_primary)),
            ],
        ),
        "debt_equity": _pick_numeric(
            "debt_equity",
            [
                (info.get("debt_equity"), _provider_source(raw_primary)),
                (info.get("debtToEquity"), _provider_source(raw_primary)),
                (info.get("debt_to_equity"), _provider_source(raw_primary)),
                (canonical.get("debt_equity"), _provider_source(raw_primary)),
            ],
        ),
        "revenue_growth": _pick_numeric(
            "revenue_growth",
            [
                (info.get("revenue_growth"), _provider_source(raw_primary)),
                (canonical.get("revenue_growth"), _provider_source(raw_primary)),
            ],
            is_percentage=True,
        ),
        "net_profit_growth": _pick_numeric(
            "net_profit_growth",
            [
                (info.get("net_profit_growth"), _provider_source(raw_primary)),
                (canonical.get("net_profit_growth"), _provider_source(raw_primary)),
            ],
            is_percentage=True,
        ),
        "foreign_ratio": _pick_numeric(
            "foreign_ratio",
            [
                (info.get("foreign_ratio"), _provider_source(raw_primary)),
                (canonical.get("foreign_ratio"), _provider_source(raw_primary)),
                (supplement.get("foreign_ratio"), _supplement_source(raw_supplements, "foreign_ratio")),
            ],
            is_percentage=True,
        ),
        "free_float": _pick_numeric(
            "free_float",
            [
                (info.get("free_float"), _provider_source(raw_primary)),
                (canonical.get("free_float"), _provider_source(raw_primary)),
                (supplement.get("free_float"), _supplement_source(raw_supplements, "free_float")),
            ],
            is_percentage=True,
        ),
        "year_high": _pick_numeric(
            "year_high",
            [
                (info.get("year_high"), _provider_source(raw_primary)),
                (info.get("fiftyTwoWeekHigh"), _provider_source(raw_primary)),
                (canonical.get("year_high"), _provider_source(raw_primary)),
            ],
        ),
        "year_low": _pick_numeric(
            "year_low",
            [
                (info.get("year_low"), _provider_source(raw_primary)),
                (info.get("fiftyTwoWeekLow"), _provider_source(raw_primary)),
                (canonical.get("year_low"), _provider_source(raw_primary)),
            ],
        ),
        "ma_50": _pick_numeric(
            "ma_50",
            [
                (info.get("ma_50"), _provider_source(raw_primary)),
                (info.get("fiftyDayAverage"), _provider_source(raw_primary)),
                (canonical.get("fifty_day_avg"), _provider_source(raw_primary)),
            ],
        ),
        "ma_200": _pick_numeric(
            "ma_200",
            [
                (info.get("ma_200"), _provider_source(raw_primary)),
                (info.get("twoHundredDayAverage"), _provider_source(raw_primary)),
                (canonical.get("two_hundred_day_avg"), _provider_source(raw_primary)),
            ],
        ),
        "market_cap": _pick_numeric(
            "market_cap",
            [
                (fast_info.get("market_cap"), _provider_source(raw_primary)),
                (info.get("marketCap"), _provider_source(raw_primary)),
                (canonical.get("market_cap"), _provider_source(raw_primary)),
            ],
        ),
        "last_price": _pick_numeric(
            "last_price",
            [
                (fast_info.get("last_price"), _provider_source(raw_primary)),
                (fast_info.get("lastPrice"), _provider_source(raw_primary)),
                (fast_info.get("last_price_value"), _provider_source(raw_primary)),
                (fast_info.get("regularMarketPrice"), _provider_source(raw_primary)),
                (info.get("currentPrice"), _provider_source(raw_primary)),
                (canonical.get("last_price"), _provider_source(raw_primary)),
            ],
        ),
        "daily_volume": _pick_numeric(
            "daily_volume",
            [
                (fast_info.get("volume"), _provider_source(raw_primary)),
                (info.get("volume"), _provider_source(raw_primary)),
                (canonical.get("volume"), _provider_source(raw_primary)),
            ],
        ),
    }

    field_sources = {
        field: value[1]
        for field, value in payload.items()
        if isinstance(value, tuple) and value[0] is not None
    }
    normalized_payload = {
        field: value[0] if isinstance(value, tuple) else value
        for field, value in payload.items()
    }
    return normalized_payload, field_sources


def _pick_numeric(
    field_name: str,
    candidates: list[tuple[Any, str | None]],
    is_percentage: bool = False,
) -> tuple[float | None, str] | tuple[None, str]:
    for raw_value, source in candidates:
        normalized = _normalize_numeric_value(field_name, raw_value, is_percentage=is_percentage)
        if normalized is not None and source:
            return normalized, source
    return None, ""


def _normalize_numeric_value(
    field_name: str,
    value: Any,
    is_percentage: bool = False,
) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        numeric_value = float(value)
        if is_percentage and field_name in PERCENTAGE_FIELDS and 1 < abs(numeric_value) <= 100:
            return numeric_value / 100
        return numeric_value
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if cleaned in {"", "-", "--", "N/A", "n/a", "null", "None"}:
        return None

    percent_marked = "%" in cleaned
    cleaned = (
        cleaned.replace("â‚º", "")
        .replace("TL", "")
        .replace("TRY", "")
        .replace("%", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")

    try:
        numeric_value = float(cleaned)
    except ValueError:
        return None

    if not math.isfinite(numeric_value):
        return None
    if is_percentage and field_name in PERCENTAGE_FIELDS:
        if percent_marked:
            return numeric_value / 100
        if 1 < abs(numeric_value) <= 100:
            return numeric_value / 100
    return numeric_value


def _coerce_raw_payload(snapshot: RawSnapshotPayload | StockSnapshot | None) -> RawSnapshotPayload | None:
    if snapshot is None:
        return None
    if isinstance(snapshot, RawSnapshotPayload):
        return snapshot

    return RawSnapshotPayload(
        symbol=snapshot.symbol,
        provider=_provider_name(snapshot),
        sections={
            "canonical": {
                "pe_ratio": snapshot.pe_ratio,
                "pb_ratio": snapshot.pb_ratio,
                "dividend_yield": snapshot.dividend_yield,
                "trailing_eps": snapshot.trailing_eps,
                "roe": snapshot.roe,
                "roa": snapshot.roa,
                "current_ratio": snapshot.current_ratio,
                "debt_equity": snapshot.debt_equity,
                "revenue_growth": getattr(snapshot, "revenue_growth", None),
                "net_profit_growth": getattr(snapshot, "net_profit_growth", None),
                "foreign_ratio": snapshot.foreign_ratio,
                "free_float": snapshot.free_float,
                "year_high": snapshot.year_high,
                "year_low": snapshot.year_low,
                "fifty_day_avg": snapshot.fifty_day_avg,
                "two_hundred_day_avg": snapshot.two_hundred_day_avg,
                "market_cap": snapshot.market_cap,
                "last_price": snapshot.last_price,
                "volume": snapshot.volume,
            }
        },
    )


def _merge_sections(payloads: list[RawSnapshotPayload], section_name: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        merged.update(payload.get_section(section_name))
    return merged


def _provider_name(snapshot: RawSnapshotPayload | StockSnapshot | None) -> str:
    if snapshot is None:
        return ""
    provider = getattr(snapshot, "provider", None)
    if provider is not None:
        return getattr(provider, "value", str(provider))
    source = getattr(snapshot, "source", None)
    return getattr(source, "value", str(source)) if source is not None else ""


def _provider_source(snapshot: RawSnapshotPayload | None) -> str | None:
    provider_name = _provider_name(snapshot)
    return f"provider:{provider_name}" if provider_name else None


def _supplement_source(payloads: list[RawSnapshotPayload], field_name: str) -> str | None:
    for payload in payloads:
        if payload.get_section("supplement").get(field_name) is not None:
            return _provider_source(payload)
    return None


def _latest_fetched_at(
    primary_snapshot: RawSnapshotPayload | None,
    supplements: list[RawSnapshotPayload],
) -> datetime:
    fetched_times = [payload.fetched_at for payload in [primary_snapshot, *supplements] if payload is not None]
    return max(fetched_times, default=datetime.now(timezone.utc))
