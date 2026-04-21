"""Raw snapshot provider backed by borsapy."""

from __future__ import annotations

from app.services.data.provider_exceptions import ProviderError, map_borsapy_exception
from app.services.data.providers.borsapy_provider import BorsapyProvider
from app.services.data.providers.snapshot_provider import RawSnapshotPayload
from app.services.utils.logging import logger


class BorsapySnapshotProvider(BorsapyProvider):
    """Fetch raw snapshot sections from borsapy for normalization."""

    provider_name = "borsapy"

    def fetch_snapshot(self, symbol: str) -> RawSnapshotPayload:
        logger.debug("Fetching raw snapshot via borsapy for %s", symbol)

        ticker = self._create_ticker(symbol)

        try:
            fast_info = ticker.fast_info
            info = ticker.info
        except Exception as exc:
            logger.error("Error loading raw borsapy snapshot for %s: %s", symbol, exc)
            if isinstance(exc, ProviderError):
                raise
            raise map_borsapy_exception(exc)

        return RawSnapshotPayload(
            symbol=symbol.upper(),
            provider=self.provider_name,
            sections={
                "fast_info": {
                    "last_price": self._safe_attr(fast_info, "last_price"),
                    "volume": self._safe_attr(fast_info, "volume"),
                    "market_cap": self._safe_attr(fast_info, "market_cap"),
                    "pe_ratio": self._safe_attr(fast_info, "pe_ratio"),
                    "pb_ratio": self._safe_attr(fast_info, "pb_ratio"),
                    "year_high": self._safe_attr(fast_info, "year_high"),
                    "year_low": self._safe_attr(fast_info, "year_low"),
                    "fifty_day_average": self._safe_attr(fast_info, "fifty_day_average"),
                    "two_hundred_day_average": self._safe_attr(fast_info, "two_hundred_day_average"),
                    "free_float": self._safe_attr(fast_info, "free_float"),
                    "foreign_ratio": self._safe_attr(fast_info, "foreign_ratio"),
                },
                "info": {
                    "change": info.get("change"),
                    "change_percent": info.get("change_percent"),
                    "currentPrice": info.get("currentPrice"),
                    "volume": info.get("volume"),
                    "market_cap": info.get("market_cap"),
                    "marketCap": info.get("marketCap"),
                    "pe_ratio": info.get("pe_ratio"),
                    "trailingPE": info.get("trailingPE"),
                    "pb_ratio": info.get("pb_ratio"),
                    "priceToBook": info.get("priceToBook"),
                    "dividend_yield": info.get("dividend_yield"),
                    "dividendYield": info.get("dividendYield"),
                    "trailing_eps": info.get("trailing_eps"),
                    "trailingEps": info.get("trailingEps"),
                    "eps": info.get("eps"),
                    "roe": info.get("roe"),
                    "returnOnEquity": info.get("returnOnEquity"),
                    "debt_equity": info.get("debt_equity"),
                    "debtToEquity": info.get("debtToEquity"),
                    "debt_to_equity": info.get("debt_to_equity"),
                    "free_float": info.get("free_float"),
                    "floatSharesPercent": info.get("floatSharesPercent"),
                    "foreign_ratio": info.get("foreign_ratio"),
                    "foreignOwnership": info.get("foreignOwnership"),
                },
            },
        )
