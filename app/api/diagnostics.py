"""
Diagnostic Centre & Test routes — CRUD with pagination.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, PaginationParams
from app.models.user import User
from app.models.diagnostic import DiagnosticCentre, DiagnosticTest
from app.schemas.diagnostic import (
    DiagnosticCentreCreate,
    DiagnosticCentreResponse,
    DiagnosticCentreListResponse,
    DiagnosticTestCreate,
    DiagnosticTestResponse,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


# ──────────────────────────────────────────────
# Centres
# ──────────────────────────────────────────────

@router.post(
    "/",
    response_model=DiagnosticCentreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic centre",
)
async def create_centre(
    payload: DiagnosticCentreCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Create a new diagnostic centre. Requires authentication."""
    centre = DiagnosticCentre(**payload.model_dump())
    db.add(centre)
    await db.flush()
    await db.refresh(centre)
    return centre


@router.get(
    "/",
    response_model=PaginatedResponse[DiagnosticCentreListResponse],
    summary="List all diagnostic centres (paginated)",
)
async def list_centres(
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
):
    """Public endpoint — list all active diagnostic centres with pagination."""
    # Count
    count_query = select(func.count()).select_from(DiagnosticCentre).where(DiagnosticCentre.is_active.is_(True))
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    query = (
        select(DiagnosticCentre)
        .where(DiagnosticCentre.is_active.is_(True))
        .order_by(DiagnosticCentre.name)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(query)
    centres = result.scalars().all()

    return PaginatedResponse(
        items=[DiagnosticCentreListResponse.model_validate(c) for c in centres],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=math.ceil(total / pagination.page_size) if total else 0,
    )


@router.get(
    "/{centre_id}",
    response_model=DiagnosticCentreResponse,
    summary="Get diagnostic centre details with tests",
    responses={404: {"description": "Centre not found"}},
)
async def get_centre(centre_id: int, db: AsyncSession = Depends(get_db)):
    """Public endpoint — retrieve a single centre with its available tests."""
    result = await db.execute(
        select(DiagnosticCentre).where(
            DiagnosticCentre.id == centre_id,
            DiagnosticCentre.is_active.is_(True),
        )
    )
    centre = result.scalar_one_or_none()
    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre with id {centre_id} not found.",
        )
    return centre


# ──────────────────────────────────────────────
# Tests (nested under centres)
# ──────────────────────────────────────────────

@router.post(
    "/{centre_id}/tests",
    response_model=DiagnosticTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a diagnostic test to a centre",
    responses={404: {"description": "Centre not found"}},
)
async def create_test(
    centre_id: int,
    payload: DiagnosticTestCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Add a new diagnostic test to a specific centre. Requires authentication."""
    # Verify centre exists
    result = await db.execute(
        select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre with id {centre_id} not found.",
        )

    test = DiagnosticTest(centre_id=centre_id, **payload.model_dump())
    db.add(test)
    await db.flush()
    await db.refresh(test)
    return test


@router.get(
    "/{centre_id}/tests",
    response_model=PaginatedResponse[DiagnosticTestResponse],
    summary="List tests for a centre (paginated)",
    responses={404: {"description": "Centre not found"}},
)
async def list_tests(
    centre_id: int,
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
):
    """Public endpoint — list all active tests for a specific centre."""
    # Verify centre exists
    result = await db.execute(
        select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre with id {centre_id} not found.",
        )

    # Count
    count_query = (
        select(func.count())
        .select_from(DiagnosticTest)
        .where(DiagnosticTest.centre_id == centre_id, DiagnosticTest.is_active.is_(True))
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch
    query = (
        select(DiagnosticTest)
        .where(DiagnosticTest.centre_id == centre_id, DiagnosticTest.is_active.is_(True))
        .order_by(DiagnosticTest.name)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    tests = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[DiagnosticTestResponse.model_validate(t) for t in tests],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=math.ceil(total / pagination.page_size) if total else 0,
    )
