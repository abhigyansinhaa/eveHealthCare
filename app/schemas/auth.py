"""
Pydantic schemas for User / Auth endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ──────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────

class UserSignupRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255, examples=["Jane Doe"])
    password: str = Field(..., min_length=8, max_length=128, examples=["SecureP@ss123"])


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


# ──────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
