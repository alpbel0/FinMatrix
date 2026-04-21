"""Best-effort snapshot supplement provider backed by pykap/KAP pages."""

from __future__ import annotations

import re

import requests

from app.services.data.provider_exceptions import ProviderSymbolNotFoundError, map_pykap_exception
from app.services.data.providers.pykap_provider import get_general_info
from app.services.data.providers.snapshot_provider import RawSnapshotPayload
from app.services.utils.logging import logger


class PykapSupplementProvider:
    """Fetch supplemental snapshot fields not reliably exposed by borsapy."""

    provider_name = "pykap"

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    def fetch_snapshot(self, symbol: str) -> RawSnapshotPayload:
        normalized_symbol = symbol.upper()
        try:
            general_info = get_general_info(normalized_symbol)
            if general_info is None:
                raise ProviderSymbolNotFoundError(normalized_symbol, provider=self.provider_name)

            supplement = {
                "free_float": None,
                "foreign_ratio": None,
            }
            summary_page = general_info.get("summary_page")
            if summary_page:
                supplement.update(self._fetch_summary_metrics(summary_page))

            return RawSnapshotPayload(
                symbol=normalized_symbol,
                provider=self.provider_name,
                sections={
                    "general_info": general_info,
                    "supplement": supplement,
                },
            )
        except Exception as exc:
            logger.debug("Pykap supplement fetch failed for %s: %s", normalized_symbol, exc)
            raise map_pykap_exception(exc)

    def _fetch_summary_metrics(self, summary_page: str) -> dict[str, str | None]:
        response = requests.get(summary_page, timeout=self._timeout)
        response.raise_for_status()
        content = response.text

        return {
            "free_float": self._extract_metric(
                content,
                labels=(
                    "Fiili Dolaşımdaki Pay Oranı",
                    "Fiili Dolasimdaki Pay Orani",
                    "Halka Açıklık Oranı",
                    "Halka Aciklik Orani",
                    "Free Float",
                ),
            ),
            "foreign_ratio": self._extract_metric(
                content,
                labels=(
                    "Yabancı Oranı",
                    "Yabanci Orani",
                    "Yabancı Pay Oranı",
                    "Yabanci Pay Orani",
                    "Foreign Ratio",
                ),
            ),
        }

    def _extract_metric(self, content: str, labels: tuple[str, ...]) -> str | None:
        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}[^0-9%]*([0-9]{{1,3}}(?:[.,][0-9]{{1,4}})?)\s*%?",
                re.IGNORECASE,
            )
            match = pattern.search(content)
            if match:
                return match.group(1)
        return None
