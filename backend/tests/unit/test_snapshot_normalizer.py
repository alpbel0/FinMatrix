"""Unit tests for raw snapshot normalization and provider composition."""

import pytest

from app.services.data.mappers.snapshot_normalizer import normalize_snapshot_payload
from app.services.data.providers.snapshot_provider import (
    CompositeSnapshotProvider,
    RawSnapshotPayload,
)


class _StaticProvider:
    def __init__(self, provider_name, payload=None, error=None):
        self.provider_name = provider_name
        self._payload = payload
        self._error = error

    def fetch_snapshot(self, symbol: str):
        if self._error:
            raise self._error
        return self._payload


class TestSnapshotNormalizer:
    def test_normalizer_applies_provider_and_supplement_fallbacks(self):
        primary = RawSnapshotPayload(
            symbol="THYAO",
            provider="borsapy",
            sections={
                "fast_info": {
                    "pe_ratio": "5,75",
                    "pb_ratio": 1.2,
                    "free_float": None,
                    "market_cap": "500.000.000.000",
                    "last_price": "289,40",
                    "volume": "1.250.000",
                },
                "info": {
                    "pe_ratio": "7,10",
                    "roe": "24,5%",
                    "foreign_ratio": "37,4%",
                },
            },
        )
        supplement = RawSnapshotPayload(
            symbol="THYAO",
            provider="pykap",
            sections={"supplement": {"free_float": "48,2", "foreign_ratio": "35,0"}},
        )

        payload = normalize_snapshot_payload(primary, supplements=[supplement])

        assert payload["pe_ratio"] == 5.75
        assert payload["pb_ratio"] == 1.2
        assert payload["roe"] == 0.245
        assert payload["foreign_ratio"] == 0.374
        assert payload["free_float"] == pytest.approx(0.482)
        assert payload["market_cap"] == 500_000_000_000
        assert payload["last_price"] == 289.4
        assert payload["daily_volume"] == 1_250_000
        assert payload["field_sources"]["free_float"] == "provider:pykap"
        assert payload["field_sources"]["pe_ratio"] == "provider:borsapy"
        assert payload["source"] == "provider:borsapy+provider:pykap"

    def test_normalizer_converts_invalid_values_to_none(self):
        primary = RawSnapshotPayload(
            symbol="THYAO",
            provider="borsapy",
            sections={
                "fast_info": {
                    "pe_ratio": "--",
                    "pb_ratio": "N/A",
                    "market_cap": "not-a-number",
                },
                "info": {
                    "dividendYield": "",
                    "roe": None,
                    "debtToEquity": "-",
                },
            },
        )

        payload = normalize_snapshot_payload(primary)

        assert payload["pe_ratio"] is None
        assert payload["pb_ratio"] is None
        assert payload["market_cap"] is None
        assert payload["dividend_yield"] is None
        assert payload["roe"] is None
        assert payload["debt_equity"] is None


class TestCompositeSnapshotProvider:
    def test_composite_provider_returns_primary_and_non_empty_supplements(self):
        primary = _StaticProvider(
            "borsapy",
            RawSnapshotPayload(symbol="THYAO", provider="borsapy", sections={"fast_info": {"pe_ratio": 5.0}}),
        )
        supplement = _StaticProvider(
            "pykap",
            RawSnapshotPayload(symbol="THYAO", provider="pykap", sections={"supplement": {"free_float": "45,0"}}),
        )

        composite = CompositeSnapshotProvider(primary=primary, supplements=[supplement])
        result = composite.fetch_snapshot("THYAO")

        assert result.primary is not None
        assert result.primary.provider == "borsapy"
        assert len(result.supplements) == 1
        assert result.supplements[0].provider == "pykap"
