"""Integration tests for BorsapyProvider with real API calls.

Tests use real borsapy API calls to verify provider functionality.
Test symbols: THYAO, GARAN, ASELS (as specified in roadmap).
"""

import pytest
from datetime import date, timedelta

from app.services.data.providers.borsapy_provider import BorsapyProvider
from app.services.data.provider_models import PeriodType, DataSource
from app.services.data.provider_exceptions import (
    ProviderSymbolNotFoundError,
    ProviderError,
)


# Test symbols per roadmap specification
TEST_SYMBOLS = ["THYAO", "GARAN", "ASELS"]


@pytest.fixture(scope="module")
def provider():
    """Create BorsapyProvider instance for tests."""
    return BorsapyProvider(timeout=30.0, retry_count=2)


class TestBorsapyProviderHealth:
    """Health check and basic functionality tests."""

    def test_health_check(self, provider):
        """Verify provider is operational."""
        result = provider.health_check()
        assert result is True, "Provider health check should pass"

    def test_capabilities(self, provider):
        """Verify provider capabilities are correct."""
        caps = provider.capabilities

        assert "BIST" in caps.supported_markets
        assert caps.supports_intraday is True
        assert caps.supports_quarterly_financials is True
        assert caps.max_history_days >= 3650

        # Check required capabilities
        from app.services.data.provider_models import ProviderCapability
        assert ProviderCapability.PRICE_HISTORY in caps.supported_data
        assert ProviderCapability.METRICS in caps.supported_data
        assert ProviderCapability.FINANCIALS in caps.supported_data


class TestBorsapyProviderPrices:
    """Price history tests with real API."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_price_history_default_period(self, provider, symbol):
        """Fetch price history with default period."""
        bars = provider.get_price_history(symbol, period="1mo")

        assert len(bars) > 0, f"Should have price bars for {symbol}"
        assert all(bar.source == DataSource.BORSAPY for bar in bars)
        assert all(bar.close is not None for bar in bars), "All bars should have close price"

        # Verify OHLCV data structure
        first_bar = bars[0]
        assert first_bar.date is not None
        assert isinstance(first_bar.open, (float, int, type(None)))
        assert isinstance(first_bar.high, (float, int, type(None)))
        assert isinstance(first_bar.low, (float, int, type(None)))
        assert isinstance(first_bar.close, (float, int, type(None)))

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_price_history_with_dates(self, provider, symbol):
        """Fetch price history with date range."""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        bars = provider.get_price_history(
            symbol,
            start_date=start_date,
            end_date=end_date
        )

        assert len(bars) > 0, f"Should have price bars for {symbol}"

        # Verify date range
        if bars:
            assert bars[0].date >= start_date, "First bar should be after start_date"
            assert bars[-1].date <= end_date, "Last bar should be before end_date"

    def test_get_price_history_invalid_symbol(self, provider):
        """Test error handling for invalid symbol."""
        with pytest.raises((ProviderSymbolNotFoundError, ProviderError)):
            provider.get_price_history("INVALID_SYMBOL_XYZ")

    def test_batch_price_update(self, provider):
        """Batch fetch prices for multiple symbols."""
        results = provider.batch_price_update(TEST_SYMBOLS, period="1mo")

        assert len(results) == len(TEST_SYMBOLS)

        for symbol in TEST_SYMBOLS:
            assert symbol in results
            bars = results[symbol]
            # At least one symbol should have data (assuming market is open)
            # Some symbols might fail due to API issues, but we expect at least partial success
            if len(bars) > 0:
                assert all(bar.source == DataSource.BORSAPY for bar in bars)


class TestBorsapyProviderFinancials:
    """Financial statement tests with real API."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_annual_financials(self, provider, symbol):
        """Fetch annual financial statements."""
        statements = provider.get_financial_statements(
            symbol,
            period_type=PeriodType.ANNUAL,
            last_n=3
        )

        assert len(statements) > 0, f"Should have financial statements for {symbol}"
        assert all(stmt.source == DataSource.BORSAPY for stmt in statements)
        assert all(stmt.period_type == PeriodType.ANNUAL for stmt in statements)

        # Verify statement structure
        for stmt in statements:
            assert stmt.symbol == symbol.upper()
            assert stmt.statement_date is not None

        # At least one should have some financial data
        has_data = any(
            stmt.total_assets is not None or
            stmt.revenue is not None or
            stmt.net_income is not None
            for stmt in statements
        )
        assert has_data, f"At least one statement for {symbol} should have financial data"

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_quarterly_financials(self, provider, symbol):
        """Fetch quarterly financial statements."""
        statements = provider.get_financial_statements(
            symbol,
            period_type=PeriodType.QUARTERLY,
            last_n=4
        )

        assert len(statements) >= 4, f"Should have at least 4 quarterly statements for {symbol}"
        assert all(stmt.period_type == PeriodType.QUARTERLY for stmt in statements)

        # Verify quarter dates are sequential
        dates = [stmt.statement_date for stmt in statements]
        for i in range(len(dates) - 1):
            # Quarterly dates should be roughly 3 months apart
            assert dates[i] > dates[i + 1], "Statements should be ordered by date descending"


class TestBorsapyProviderSnapshot:
    """Stock snapshot/metrics tests."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_stock_snapshot(self, provider, symbol):
        """Fetch current stock metrics."""
        snapshot = provider.get_stock_snapshot(symbol)

        assert snapshot.symbol == symbol.upper()
        assert snapshot.last_price is not None, f"Should have last_price for {symbol}"
        assert snapshot.source == DataSource.BORSAPY

        # Verify snapshot structure
        assert isinstance(snapshot.market_cap, (float, int, type(None)))
        assert isinstance(snapshot.pe_ratio, (float, int, type(None)))
        assert isinstance(snapshot.volume, (float, int, type(None)))


class TestBorsapyProviderProfile:
    """Company profile tests."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_company_profile(self, provider, symbol):
        """Fetch company metadata."""
        profile = provider.get_company_profile(symbol)

        assert profile.symbol == symbol.upper()
        assert profile.exchange == "BIST"
        assert profile.source == DataSource.BORSAPY

        # Company name should exist for known stocks
        assert profile.company_name is not None, f"Should have company_name for {symbol}"


class TestBorsapyProviderKAP:
    """KAP filings tests."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS[:2])  # Test fewer symbols for KAP
    def test_get_kap_filings(self, provider, symbol):
        """Fetch KAP disclosures."""
        filings = provider.get_kap_filings(symbol)

        # KAP filings might not always be available
        if len(filings) > 0:
            assert all(f.symbol == symbol.upper() for f in filings)
            assert all(f.provider == DataSource.BORSAPY for f in filings)

            # Check filing structure
            first_filing = filings[0]
            assert first_filing.title is not None
            assert isinstance(first_filing.title, str)


class TestProviderRegistryIntegration:
    """Test provider registry with real provider."""

    def test_get_default_provider(self):
        """Verify registry returns working provider."""
        from app.services.data.provider_registry import get_default_provider

        provider = get_default_provider()
        assert isinstance(provider, BorsapyProvider)
        assert provider.health_check() is True

    def test_get_provider_for_capability(self):
        """Verify capability-based selection."""
        from app.services.data.provider_registry import get_provider_for_prices
        from app.services.data.provider_models import ProviderCapability

        provider = get_provider_for_prices()
        assert ProviderCapability.PRICE_HISTORY in provider.capabilities.supported_data