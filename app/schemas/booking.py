"""
Pydantic schemas for Booking endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    test_id: int = Field(..., gt=0)
    centre_id: int = Field(..., gt=0)
    appointment_date: datetime = Field(
        ..., examples=["2026-10-15T10:30:00+05:30"],
        description="Must be a future date/time.",
    )


class BookingResponse(BaseModel):
    id: int
    user_id: int
    test_id: int
    centre_id: int
    appointment_date: datetime
    amount: float
    status: BookingStatus
    created_at: datetime
    updated_at: datetime

    # Nested info
    test_name: str | None = None
    centre_name: str | None = None
    user_email: str | None = None

    model_config = {"from_attributes": True}


class BookingCancelRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)
