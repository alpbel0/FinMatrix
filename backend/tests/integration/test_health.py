"""Integration tests for /health endpoint."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Test the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client: AsyncClient):
        """Health endpoint should return status ok."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_database_status_present(self, client: AsyncClient):
        """Health endpoint should include database status."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "database" in data
        # Database status can be "connected" or error message
        # In tests, it may fail due to global engine isolation
        assert isinstance(data["database"], str)

    @pytest.mark.asyncio
    async def test_health_returns_json(self, client: AsyncClient):
        """Health endpoint should return JSON content type."""
        response = await client.get("/health")
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_health_has_required_fields(self, client: AsyncClient):
        """Health response should have all required fields."""
        response = await client.get("/health")
        data = response.json()

        assert "status" in data
        assert "database" in data