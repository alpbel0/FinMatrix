"""Custom exceptions for provider operations."""

from datetime import date


class ProviderError(Exception):
    """Base exception for all provider-related errors."""

    def __init__(self, message: str, provider: str | None = None):
        self.provider = provider
        super().__init__(f"[{provider}] {message}" if provider else message)


class ProviderConnectionError(ProviderError):
    """Raised when unable to connect to data source."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a request exceeds timeout limit."""

    def __init__(self, timeout_seconds: float, provider: str | None = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Request timed out after {timeout_seconds}s",
            provider
        )


class ProviderRateLimitError(ProviderError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        retry_after: int | None = None,
        provider: str | None = None
    ):
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(msg, provider)


class ProviderDataNotFoundError(ProviderError):
    """Raised when requested data is not available."""

    def __init__(
        self,
        symbol: str,
        data_type: str = "price",
        provider: str | None = None
    ):
        self.symbol = symbol
        self.data_type = data_type
        super().__init__(
            f"{data_type} data not found for symbol: {symbol}",
            provider
        )


class ProviderSymbolNotFoundError(ProviderError):
    """Raised when ticker symbol is invalid/not found."""

    def __init__(self, symbol: str, provider: str | None = None):
        self.symbol = symbol
        super().__init__(f"Symbol not found: {symbol}", provider)


class ProviderInvalidPeriodError(ProviderError):
    """Raised when invalid period/interval is specified."""

    def __init__(self, period: str, valid_periods: list[str], provider: str | None = None):
        self.period = period
        self.valid_periods = valid_periods
        super().__init__(
            f"Invalid period '{period}'. Valid: {', '.join(valid_periods)}",
            provider
        )


class ProviderAPIError(ProviderError):
    """Raised when external API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider: str | None = None
    ):
        self.status_code = status_code
        msg = f"API error: {message}"
        if status_code:
            msg += f" (status: {status_code})"
        super().__init__(msg, provider)


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication fails."""
    pass


class ProviderPartialDataError(ProviderError):
    """Raised when batch operation returns partial results."""

    def __init__(
        self,
        successful: list[str],
        failed: dict[str, str],
        provider: str | None = None
    ):
        self.successful = successful
        self.failed = failed
        super().__init__(
            f"Partial data: {len(successful)} succeeded, {len(failed)} failed",
            provider
        )


def map_borsapy_exception(exc: Exception) -> ProviderError:
    """Map borsapy exceptions to provider exceptions."""
    # Import borsapy exceptions if available
    try:
        from borsapy.exceptions import (
            TickerNotFoundError,
            DataNotAvailableError,
            APIError,
            RateLimitError,
            AuthenticationError,
        )

        if isinstance(exc, TickerNotFoundError):
            symbol = getattr(exc, 'symbol', 'unknown')
            return ProviderSymbolNotFoundError(symbol, provider="borsapy")
        if isinstance(exc, DataNotAvailableError):
            return ProviderDataNotFoundError(
                symbol="unknown",
                data_type="data",
                provider="borsapy"
            )
        if isinstance(exc, RateLimitError):
            retry_after = getattr(exc, 'retry_after', None)
            return ProviderRateLimitError(retry_after=retry_after, provider="borsapy")
        if isinstance(exc, AuthenticationError):
            return ProviderAuthenticationError(
                "Borsapy authentication failed",
                provider="borsapy"
            )
        if isinstance(exc, APIError):
            status_code = getattr(exc, 'status_code', None)
            return ProviderAPIError(
                str(exc),
                status_code=status_code,
                provider="borsapy"
            )
    except ImportError:
        # borsapy exceptions module not available
        pass

    # Fallback: wrap any exception as generic ProviderError
    return ProviderError(str(exc), provider="borsapy")