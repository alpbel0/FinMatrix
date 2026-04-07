"""Authentication service for password hashing, JWT tokens, and user operations."""

import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.schemas.auth import RegisterRequest

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    # bcrypt requires bytes, encode password and return decoded hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with optional expiry."""
    to_encode = data.copy()
    # Convert user_id to string for JWT subject claim
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token, returning the payload."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return payload


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Find a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Find a user by username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Find a user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, user_data: RegisterRequest) -> User:
    """Register a new user with hashed password."""
    # Check if email already exists
    existing_email = await get_user_by_email(db, user_data.email)
    if existing_email:
        raise ValueError("Email already registered")

    # Check if username already exists
    existing_username = await get_user_by_username(db, user_data.username)
    if existing_username:
        raise ValueError("Username already taken")

    # Create user with hashed password
    hashed_password = hash_password(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        is_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_current_user(db: AsyncSession, token: str) -> User:
    """Get the current user from a JWT token."""
    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise ValueError("Invalid token: missing user ID")
        user_id = int(user_id_str)
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
    except ValueError as e:
        raise ValueError("Invalid token: user ID must be an integer") from e

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    return user