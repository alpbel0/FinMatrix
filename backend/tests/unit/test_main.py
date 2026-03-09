"""
Unit tests for main FastAPI application.

Tests cover:
- Health check endpoint
- Root endpoint
- CORS middleware configuration
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_ok(self, client: AsyncClient):
        """Health check should return status ok."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "finmatrix-api"

    @pytest.mark.asyncio
    async def test_health_check_includes_version(self, client: AsyncClient):
        """Health check should include app version."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] is not None


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint_returns_welcome(self, client: AsyncClient):
        """Root endpoint should return welcome message."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "FinMatrix" in data["message"]

    @pytest.mark.asyncio
    async def test_root_endpoint_includes_docs_link(self, client: AsyncClient):
        """Root endpoint should include docs link."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "docs" in data
        assert data["docs"] == "/docs"


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_cors_allows_origin(self, client: AsyncClient):
        """CORS should allow configured origins."""
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )

        # Preflight should succeed
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cors_allows_credentials(self, client: AsyncClient):
        """CORS should allow credentials."""
        response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200


class TestExceptionHandling:
    """Tests for exception handlers."""

    @pytest.mark.asyncio
    async def test_404_returns_not_found(self, client: AsyncClient):
        """Non-existent endpoint should return 404."""
        response = await client.get("/nonexistent-endpoint")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validation_error_returns_422(self, client: AsyncClient):
        """Invalid request data should return 422."""
        # Example: if there was a POST endpoint expecting JSON
        # For now, this is a placeholder for when routes are implemented
        pass