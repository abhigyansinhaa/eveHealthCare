"""
Pydantic schemas for Payment and Webhook endpoints.
"""

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus


class PaymentCreateRequest(BaseModel):
    booking_id: int = Field(..., gt=0)


class PaymentResponse(BaseModel):
    id: int
    transaction_id: str
    booking_id: int
    amount: float
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    """
    Simulated payment provider webhook payload.

    The transaction_id is used for idempotency — replayed webhooks
    with the same transaction_id will not corrupt state.
    """
    transaction_id: str = Field(..., min_length=1, max_length=36)
    status: Literal["SUCCESS", "FAILED"] = Field(
        ..., description="Payment outcome: SUCCESS or FAILED (PENDING is invalid for webhook)"
    )


class WebhookResponse(BaseModel):
    message: str
    transaction_id: str
    booking_id: int
    payment_status: PaymentStatus
    booking_status: str
