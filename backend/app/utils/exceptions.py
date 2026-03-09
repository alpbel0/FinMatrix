"""Custom exceptions for FinMatrix application."""

from fastapi import HTTPException, status


class FinMatrixError(Exception):
    """Base exception for FinMatrix."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(FinMatrixError):
    """Resource not found."""

    pass


class AuthError(FinMatrixError):
    """Authentication/Authorization error."""

    pass


class ExternalAPIError(FinMatrixError):
    """External API (yfinance, KAP) error."""

    pass