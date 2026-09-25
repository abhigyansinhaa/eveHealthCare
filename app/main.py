"""
EVE Healthcare — Main FastAPI Application

Diagnostic Test Booking & Simulated Payment Service
"""

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import auth_router, diagnostics_router, bookings_router, payments_router

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup (for development convenience)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend service for diagnostic test bookings with simulated payments.\n\n"
        "**Features:**\n"
        "- JWT-based authentication (signup/login)\n"
        "- Diagnostic centre & test management\n"
        "- Booking system with state management\n"
        "- Simulated payment processing\n"
        "- Idempotent payment webhook\n"
        "- Pagination on list endpoints"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ──────────────────────────────────────────────
# Global exception handlers
# ──────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a cleaner 422 response with structured error details."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed.",
            "errors": errors,
        },
    )


# ──────────────────────────────────────────────
# Register routers
# ──────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(diagnostics_router)
app.include_router(bookings_router)
app.include_router(payments_router)


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Service health check")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


# ──────────────────────────────────────────────
# Interactive Web Dashboard (Frontend)
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["Frontend"], summary="Interactive Web Dashboard")
@app.get("/dashboard", response_class=HTMLResponse, tags=["Frontend"], summary="Interactive Web Dashboard")
async def serve_dashboard():
    """Serves the single-page application dashboard for testing & managing bookings."""
    if INDEX_HTML.exists():
        return HTMLResponse(content=INDEX_HTML.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>EVE HealthCare API</h1><p>Visit <a href='/docs'>/docs</a></p>")
