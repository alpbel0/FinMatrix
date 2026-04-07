"""Integration tests for auth endpoints."""

import pytest
from httpx import AsyncClient


class TestRegisterEndpoint:
    """Test POST /api/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Successful registration should return token."""
        response = await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "test@example.com", "password": "password123"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Duplicate email should return 400."""
        # First registration
        await client.post(
            "/api/auth/register",
            json={"username": "user1", "email": "same@example.com", "password": "password123"}
        )
        # Second registration with same email
        response = await client.post(
            "/api/auth/register",
            json={"username": "user2", "email": "same@example.com", "password": "password123"}
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Duplicate username should return 400."""
        # First registration
        await client.post(
            "/api/auth/register",
            json={"username": "sameuser", "email": "email1@example.com", "password": "password123"}
        )
        # Second registration with same username
        response = await client.post(
            "/api/auth/register",
            json={"username": "sameuser", "email": "email2@example.com", "password": "password123"}
        )
        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]


class TestLoginEndpoint:
    """Test POST /api/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Successful login should return token."""
        # Register first
        await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "test@example.com", "password": "password123"}
        )
        # Login
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Wrong password should return 401."""
        # Register first
        await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "test@example.com", "password": "password123"}
        )
        # Login with wrong password
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Nonexistent user should return 401."""
        response = await client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"}
        )
        assert response.status_code == 401


class TestMeEndpoint:
    """Test GET /api/auth/me."""

    @pytest.mark.asyncio
    async def test_me_with_valid_token(self, client: AsyncClient):
        """Valid token should return user data."""
        # Register
        register_response = await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "test@example.com", "password": "password123"}
        )
        token = register_response.json()["access_token"]

        # Get me
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "is_admin" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_me_without_token(self, client: AsyncClient):
        """Missing token should return 401."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401  # HTTPBearer returns 401 for missing token

    @pytest.mark.asyncio
    async def test_me_with_invalid_token(self, client: AsyncClient):
        """Invalid token should return 401."""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401