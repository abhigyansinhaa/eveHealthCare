"""
Payment routes — simulated payment processing and idempotent webhook.
"""

import hashlib
import hmac
import random

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentResponse,
    WebhookPayload,
    WebhookResponse,
)

settings = get_settings()

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a simulated payment",
    responses={
        400: {"description": "Invalid booking state"},
        403: {"description": "Not your booking"},
        404: {"description": "Booking not found"},
        409: {"description": "A payment already exists for this booking"},
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
    - Locks the booking row (FOR UPDATE) to serialize concurrent requests.
    - Randomly simulates SUCCESS (70%) or FAILED (30%) outcome.
    - Updates the booking status accordingly.
    - A booking can only have one payment record (UNIQUE constraint).
      Concurrent or duplicate attempts return 409 Conflict.
    """
    # Fetch booking with row lock
    result = await db.execute(
        select(Booking).where(Booking.id == payload.booking_id).with_for_update()
    )
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

    # Check for existing payment (prevent duplicates)
    result = await db.execute(
        select(Payment).where(Payment.booking_id == payload.booking_id)
    )
    existing_payment = result.scalar_one_or_none()
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A payment already exists for this booking (transaction: {existing_payment.transaction_id}).",
        )

    # State check
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot process payment for a booking with status '{booking.status.value}'. Only PENDING bookings can be paid.",
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

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A payment already exists for this booking.",
        )

    await db.refresh(payment)
    return payment


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details by ID",
    responses={
        404: {"description": "Payment not found"},
        403: {"description": "Not your payment"},
    },
)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details of a specific payment."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with id {payment_id} not found.",
        )

    # Check ownership via booking
    result = await db.execute(select(Booking).where(Booking.id == payment.booking_id))
    booking = result.scalar_one_or_none()
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this payment.",
        )

    return payment


@router.post(
    "/webhook/",
    response_model=WebhookResponse,
    summary="Payment provider webhook (idempotent)",
    responses={
        401: {"description": "Missing or invalid webhook signature"},
        404: {"description": "Transaction or booking not found"},
    },
)
async def payment_webhook(
    request: Request,
    payload: WebhookPayload,
    x_signature: str | None = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Receives payment status updates from a simulated payment provider.

    **Security:**
    - Authenticates via HMAC-SHA256 signature in `X-Signature` header calculated
      from the raw request body using WEBHOOK_SECRET.

    **Idempotency & Reconciliation guarantees:**
    - The webhook serves as the reconciliation path for late or out-of-order provider events.
    - Uses row-level locking (`with_for_update`) to prevent race conditions.
    - Terminal payment states (SUCCESS/FAILED) are immutable and cannot be overridden.
    - If the payment already has this status, returns success without changes.
    """
    # 1. Verify webhook signature
    if not x_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Signature header.",
        )

    raw_body = await request.body()
    expected_sig = hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(x_signature, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    # 2. Find payment by transaction_id with row lock
    result = await db.execute(
        select(Payment).where(Payment.transaction_id == payload.transaction_id).with_for_update()
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No payment found with transaction_id '{payload.transaction_id}'.",
        )

    # 3. Fetch the associated booking with row lock
    result = await db.execute(
        select(Booking).where(Booking.id == payment.booking_id).with_for_update()
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated booking not found.",
        )

    # 4. Idempotency check: if payment already has this status, return without changes
    if payment.status == payload.status:
        return WebhookResponse(
            message="Webhook already processed (idempotent — no changes made).",
            transaction_id=payment.transaction_id,
            booking_id=booking.id,
            payment_status=payment.status,
            booking_status=booking.status.value,
        )

    # 5. Guard: do not allow transitions away from terminal states (terminal states are immutable)
    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
        return WebhookResponse(
            message=f"Payment is already in terminal state '{payment.status.value}'. No update applied.",
            transaction_id=payment.transaction_id,
            booking_id=booking.id,
            payment_status=payment.status,
            booking_status=booking.status.value,
        )

    # 6. Apply status update (reconciliation path for pending payments)
    payment.status = PaymentStatus(payload.status)

    if payload.status == "SUCCESS":
        booking.status = BookingStatus.CONFIRMED
    elif payload.status == "FAILED":
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
