from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db_session)):
    """Register a new user and return an access token."""
    try:
        user = await register_user(db, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    """Authenticate a user and return an access token."""
    user = await authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session),
):
    """Get the current authenticated user."""
    try:
        user = await get_current_user(db, credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
