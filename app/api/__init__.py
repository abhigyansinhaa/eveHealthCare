from app.api.auth import router as auth_router
from app.api.diagnostics import router as diagnostics_router
from app.api.bookings import router as bookings_router
from app.api.payments import router as payments_router

__all__ = ["auth_router", "diagnostics_router", "bookings_router", "payments_router"]
