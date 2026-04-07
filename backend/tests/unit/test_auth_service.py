"""Unit tests for auth_service module."""

import pytest
from datetime import timedelta

from app.services.auth_service import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import get_settings


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password_returns_string(self):
        """hash_password should return a string."""
        hashed = hash_password("testpassword")
        assert isinstance(hashed, str)
        assert hashed != "testpassword"

    def test_hash_password_creates_different_hashes(self):
        """Different passwords should have different hashes."""
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        hashed = hash_password("testpassword")
        assert verify_password("testpassword", hashed) is True

    def test_verify_password_wrong(self):
        """verify_password should return False for wrong password."""
        hashed = hash_password("testpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_bcrypt_format(self):
        """Hash should follow bcrypt format."""
        hashed = hash_password("testpassword")
        # bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")


class TestJWTToken:
    """Test JWT token functions."""

    def test_create_access_token_returns_string(self):
        """create_access_token should return a string."""
        token = create_access_token({"sub": "1"})
        assert isinstance(token, str)

    def test_decode_token_returns_payload(self):
        """decode_token should return the original payload with sub as string."""
        data = {"sub": "42", "email": "test@example.com"}
        token = create_access_token(data)
        decoded = decode_token(token)
        assert decoded["sub"] == "42"
        assert decoded["email"] == "test@example.com"

    def test_token_with_custom_expiry(self):
        """Token with custom expiry should work."""
        token = create_access_token({"sub": "1"}, timedelta(minutes=30))
        decoded = decode_token(token)
        assert decoded["sub"] == "1"

    def test_decode_invalid_token_raises(self):
        """decode_token should raise JWTError for invalid token."""
        from jose import JWTError
        with pytest.raises(JWTError):
            decode_token("invalid_token_string")

    def test_token_contains_expiry(self):
        """Token should contain exp field."""
        token = create_access_token({"sub": "1"})
        decoded = decode_token(token)
        assert "exp" in decoded

    def test_token_with_integer_sub_converts_to_string(self):
        """Token with integer sub should be converted to string."""
        token = create_access_token({"sub": 123})
        decoded = decode_token(token)
        assert decoded["sub"] == "123"
        assert isinstance(decoded["sub"], str)