"""
Booking routes — create, list, get, and cancel bookings.
"""

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, PaginationParams
from app.models.user import User
from app.models.diagnostic import DiagnosticCentre, DiagnosticTest
from app.models.booking import Booking, BookingStatus
from app.schemas.booking import BookingCreate, BookingResponse, BookingCancelRequest
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _booking_to_response(booking: Booking) -> BookingResponse:
    """Map a Booking ORM object to its response schema with nested names."""
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        test_id=booking.test_id,
        centre_id=booking.centre_id,
        appointment_date=booking.appointment_date,
        amount=booking.amount,
        status=booking.status,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        test_name=booking.test.name if booking.test else None,
        centre_name=booking.centre.name if booking.centre else None,
        user_email=booking.user.email if booking.user else None,
    )


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a diagnostic test",
    responses={
        404: {"description": "Test or centre not found"},
        400: {"description": "Validation error (e.g., past date, test not at centre)"},
    },
)
async def create_booking(
    payload: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new booking for a diagnostic test at a specific centre.

    The appointment date must be in the future. The test must belong to the
    specified centre.
    """
    # Validate appointment is in the future
    if payload.appointment_date <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment date must be in the future.",
        )

    # Validate centre exists
    result = await db.execute(
        select(DiagnosticCentre).where(
            DiagnosticCentre.id == payload.centre_id,
            DiagnosticCentre.is_active.is_(True),
        )
    )
    centre = result.scalar_one_or_none()
    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre with id {payload.centre_id} not found.",
        )

    # Validate test exists and belongs to the centre
    result = await db.execute(
        select(DiagnosticTest).where(
            DiagnosticTest.id == payload.test_id,
            DiagnosticTest.centre_id == payload.centre_id,
            DiagnosticTest.is_active.is_(True),
        )
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic test with id {payload.test_id} not found at centre {payload.centre_id}.",
        )

    booking = Booking(
        user_id=current_user.id,
        test_id=test.id,
        centre_id=centre.id,
        appointment_date=payload.appointment_date,
        amount=float(test.price),
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)

    return _booking_to_response(booking)


@router.get(
    "/",
    response_model=PaginatedResponse[BookingResponse],
    summary="List current user's bookings (paginated)",
)
async def list_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
):
    """List all bookings for the authenticated user, newest first."""
    count_query = (
        select(func.count())
        .select_from(Booking)
        .where(Booking.user_id == current_user.id)
    )
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    bookings = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[_booking_to_response(b) for b in bookings],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=math.ceil(total / pagination.page_size) if total else 0,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get booking details",
    responses={
        404: {"description": "Booking not found"},
        403: {"description": "Not your booking"},
    },
)
async def get_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details of a specific booking. Users can only view their own bookings."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found.",
        )

    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this booking.",
        )

    return _booking_to_response(booking)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    responses={
        404: {"description": "Booking not found"},
        403: {"description": "Not your booking"},
        400: {"description": "Booking cannot be cancelled"},
    },
)
async def cancel_booking(
    booking_id: int,
    _payload: BookingCancelRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a booking. Only PENDING bookings can be cancelled.
    CONFIRMED/FAILED/CANCELLED bookings cannot be cancelled.
    """
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found.",
        )

    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to cancel this booking.",
        )

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a booking with status '{booking.status.value}'. Only PENDING bookings can be cancelled.",
        )

    booking.status = BookingStatus.CANCELLED
    await db.flush()
    await db.refresh(booking)

    return _booking_to_response(booking)
