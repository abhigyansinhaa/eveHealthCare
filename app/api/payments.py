"""
Payment routes — simulated payment processing and idempotent webhook.
"""

import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreateRequest, PaymentResponse, WebhookPayload, WebhookResponse

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a simulated payment",
    responses={
        404: {"description": "Booking not found"},
        400: {"description": "Invalid booking state or payment already exists"},
        403: {"description": "Not your booking"},
    },
)
async def create_payment(
    payload: PaymentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulate a payment for a booking.

    - Only PENDING bookings can be paid.
    - Randomly simulates SUCCESS (70%) or FAILED (30%) outcome.
    - Updates the booking status accordingly.
    - A booking can only have one payment record (prevents duplicates).
    """
    # Fetch booking
    result = await db.execute(select(Booking).where(Booking.id == payload.booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {payload.booking_id} not found.",
        )

    # Ownership check
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to pay for this booking.",
        )

    # State check
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot process payment for a booking with status '{booking.status.value}'. Only PENDING bookings can be paid.",
        )

    # Check for existing payment (prevent duplicates)
    result = await db.execute(
        select(Payment).where(Payment.booking_id == payload.booking_id)
    )
    existing_payment = result.scalar_one_or_none()
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A payment already exists for this booking (transaction: {existing_payment.transaction_id}).",
        )

    # Simulate payment outcome: 70% success, 30% failure
    payment_status = (
        PaymentStatus.SUCCESS if random.random() < 0.7 else PaymentStatus.FAILED
    )

    # Create payment record
    payment = Payment(
        booking_id=booking.id,
        amount=float(booking.amount),
        status=payment_status,
    )
    db.add(payment)

    # Update booking status based on payment outcome
    booking.status = (
        BookingStatus.CONFIRMED if payment_status == PaymentStatus.SUCCESS
        else BookingStatus.FAILED
    )

    await db.flush()
    await db.refresh(payment)

    return payment


@router.post(
    "/webhook/",
    response_model=WebhookResponse,
    summary="Payment provider webhook (idempotent)",
    responses={
        404: {"description": "Transaction not found"},
    },
)
async def payment_webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Receives payment status updates from a simulated payment provider.

    **Idempotency guarantees:**
    - If the payment has already been updated to the same status, the webhook
      returns success without making any changes.
    - Replayed webhooks will NOT create duplicate payments or corrupt state.
    - Terminal payment states (SUCCESS/FAILED) cannot be overridden.

    This endpoint is intentionally **unauthenticated** (as real payment
    webhooks are server-to-server calls authenticated via signatures/secrets).
    """
    # Find payment by transaction_id
    result = await db.execute(
        select(Payment).where(Payment.transaction_id == payload.transaction_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No payment found with transaction_id '{payload.transaction_id}'.",
        )

    # Fetch the associated booking
    result = await db.execute(select(Booking).where(Booking.id == payment.booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated booking not found.",
        )

    # Idempotency check: if payment already has this status, return without changes
    if payment.status == payload.status:
        return WebhookResponse(
            message="Webhook already processed (idempotent — no changes made).",
            transaction_id=payment.transaction_id,
            booking_id=booking.id,
            payment_status=payment.status,
            booking_status=booking.status.value,
        )

    # Guard: do not allow transitions away from terminal states
    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
        return WebhookResponse(
            message=f"Payment is already in terminal state '{payment.status.value}'. No update applied.",
            transaction_id=payment.transaction_id,
            booking_id=booking.id,
            payment_status=payment.status,
            booking_status=booking.status.value,
        )

    # Apply the status update
    payment.status = payload.status

    if payload.status == PaymentStatus.SUCCESS:
        booking.status = BookingStatus.CONFIRMED
    elif payload.status == PaymentStatus.FAILED:
        booking.status = BookingStatus.FAILED

    await db.flush()
    await db.refresh(payment)
    await db.refresh(booking)

    return WebhookResponse(
        message="Payment status updated successfully.",
        transaction_id=payment.transaction_id,
        booking_id=booking.id,
        payment_status=payment.status,
        booking_status=booking.status.value,
    )
