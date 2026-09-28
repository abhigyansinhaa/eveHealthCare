"""
Authentication routes — signup and login.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import UserSignupRequest, UserLoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"description": "Email already registered"},
    },
)
async def signup(payload: UserSignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account and return a JWT access token.

    - **email**: Must be a valid, unique email address.
    - **full_name**: User's full name (1 to 255 chars).
    - **password**: Minimum 8 characters.
    """
    # Check for existing user
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and get access token",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user with email and password. Returns a JWT access token.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/token", include_in_schema=False)
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Form-based authentication endpoint for OpenAPI/Swagger UI 'Authorize' button.
    Accepts application/x-www-form-urlencoded username & password.
    """
    return await login(UserLoginRequest(email=form.username, password=form.password), db)