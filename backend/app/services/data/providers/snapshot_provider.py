"""Snapshot provider abstractions and composition helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.services.data.provider_exceptions import ProviderError
from app.services.utils.logging import logger


class RawSnapshotPayload(BaseModel):
    """Raw, provider-shaped snapshot payload before normalization."""

    symbol: str
    provider: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sections: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def get_section(self, section_name: str) -> dict[str, Any]:
        return self.sections.get(section_name, {})

    def has_values(self) -> bool:
        for section in self.sections.values():
            for value in section.values():
                if value is not None:
                    return True
        return False


class SnapshotFetchResult(BaseModel):
    """Primary snapshot plus optional supplement payloads."""

    primary: RawSnapshotPayload | None = None
    supplements: list[RawSnapshotPayload] = Field(default_factory=list)


@runtime_checkable
class SnapshotProvider(Protocol):
    """Contract for single-symbol raw snapshot providers."""

    provider_name: str

    def fetch_snapshot(self, symbol: str) -> RawSnapshotPayload:
        """Fetch raw snapshot data for one symbol."""
        ...


class CompositeSnapshotProvider:
    """Primary snapshot provider with optional best-effort supplements."""

    def __init__(
        self,
        primary: SnapshotProvider,
        supplements: Sequence[SnapshotProvider] | None = None,
    ) -> None:
        self._primary = primary
        self._supplements = list(supplements or [])

    def fetch_snapshot(self, symbol: str) -> SnapshotFetchResult:
        primary = self._primary.fetch_snapshot(symbol)
        supplements: list[RawSnapshotPayload] = []

        for provider in self._supplements:
            try:
                payload = provider.fetch_snapshot(symbol)
                if payload.has_values():
                    supplements.append(payload)
            except ProviderError as exc:
                logger.info(
                    "Snapshot supplement skipped for %s via %s: %s",
                    symbol,
                    provider.provider_name,
                    exc,
                )
            except Exception:
                logger.exception(
                    "Unexpected snapshot supplement failure for %s via %s",
                    symbol,
                    provider.provider_name,
                )

        return SnapshotFetchResult(primary=primary, supplements=supplements)


@lru_cache(maxsize=1)
def get_snapshot_provider() -> CompositeSnapshotProvider:
    """Return the configured snapshot provider chain."""
    from app.services.data.providers.borsapy_snapshot_provider import BorsapySnapshotProvider
    from app.services.data.providers.pykap_supplement_provider import PykapSupplementProvider

    return CompositeSnapshotProvider(
        primary=BorsapySnapshotProvider(),
        supplements=[PykapSupplementProvider()],
    )
