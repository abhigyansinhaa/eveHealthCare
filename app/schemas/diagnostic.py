"""
Pydantic schemas for Diagnostic Centres and Tests.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Diagnostic Test schemas
# ──────────────────────────────────────────────

class DiagnosticTestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Complete Blood Count"])
    description: str | None = Field(None, max_length=1000)
    price: float = Field(..., gt=0, examples=[499.99])
    duration_minutes: int | None = Field(None, gt=0, examples=[30])


class DiagnosticTestResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    duration_minutes: int | None
    is_active: bool
    centre_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Diagnostic Centre schemas
# ──────────────────────────────────────────────

class DiagnosticCentreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["EVE Diagnostics — South Delhi"])
    location: str = Field(..., min_length=1, max_length=500, examples=["123 Health St, New Delhi"])
    description: str | None = Field(None, max_length=1000)


class DiagnosticCentreResponse(BaseModel):
    id: int
    name: str
    location: str
    description: str | None
    is_active: bool
    created_at: datetime
    tests: list[DiagnosticTestResponse] = []

    model_config = {"from_attributes": True}


class DiagnosticCentreListResponse(BaseModel):
    """Centre without nested tests — for list endpoints."""
    id: int
    name: str
    location: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
