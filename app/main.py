"""
EVE Healthcare — Main FastAPI Application

Diagnostic Test Booking & Simulated Payment Service
"""

from contextlib import asynccontextmanager

import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import auth_router, diagnostics_router, bookings_router, payments_router

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

settings = get_settings()

logger = logging.getLogger("eve_healthcare")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)


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
# Observability Middleware (X-Request-ID & Timing)
# ──────────────────────────────────────────────

@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    """Inject or propagate X-Request-ID and log request completion latency."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

    logger.info(
        f"req_id={request_id} method={request.method} path={request.url.path} "
        f"status={response.status_code} latency={duration_ms:.2f}ms"
    )
    return response


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
