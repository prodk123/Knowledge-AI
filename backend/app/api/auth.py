"""API routes for authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_db_session, get_current_user, get_settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.auth import LoginRequest, RegisterRequest, Token, UserResponse, User
from app.services.auth_service import AuthService, UserAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=Token)
async def login(
    request: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Authenticate user and return JWT."""
    user = await auth_service.authenticate_user(request.email, request.password, verify_password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
        
    access_token = create_access_token(subject=user.id, settings=settings)
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Get current authenticated user's profile."""
    return current_user


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Register a new user account.

    - Password is hashed server-side with bcrypt; plaintext is never persisted.
    - The new account receives the least-privileged USER role — the client cannot
      specify or escalate the role.
    - Returns a JWT access token immediately so the user is logged in on success
      (reuses the same JWT mechanism as /login — no second auth system).
    - Returns HTTP 409 if the email is already registered.
    - Returns HTTP 400 if the password is less than 8 characters.
    """
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )
    try:
        user = await auth_service.register_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            hash_password_fn=get_password_hash,
        )
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Issue a JWT token using the same mechanism as /login
    access_token = create_access_token(subject=user.id, settings=settings)
    return {"access_token": access_token, "token_type": "bearer"}
