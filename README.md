# 🏥 EVE Healthcare — Diagnostic Test Booking & Payment Service

A backend service for diagnostic test bookings with simulated payments, built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy (async)**.

---

## 📋 Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Docker (Recommended)](#docker-recommended)
  - [Local Setup](#local-setup)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Example Requests](#example-requests)
- [Running Tests](#running-tests)
- [Design Decisions & Assumptions](#design-decisions--assumptions)
- [What I Would Improve](#what-i-would-improve)

---

## Features

| Feature | Status |
|---------|--------|
| Interactive Web Dashboard (SPA) | ✅ |
| JWT Authentication (signup/login) | ✅ |
| Diagnostic Centres & Tests CRUD | ✅ |
| Booking System with state management | ✅ |
| Simulated Payment Processing | ✅ |
| Idempotent Payment Webhook | ✅ |
| Edge Case Handling | ✅ |
| Swagger/OpenAPI Documentation | ✅ |
| Docker & docker-compose | ✅ |
| Unit & Integration Tests (52 tests) | ✅ |
| Pagination | ✅ |
| Row-Level Locking & Concurrency Protection | ✅ |
| HMAC-SHA256 Webhook Verification | ✅ |

---

## Tech Stack

- **Framework**: FastAPI 0.115
- **Database**: PostgreSQL 16 (async via `asyncpg`)
- **ORM**: SQLAlchemy 2.0 (async)
- **Auth**: JWT (`python-jose`) + bcrypt (`passlib`)
- **Testing**: pytest + httpx + aiosqlite (in-memory SQLite)
- **Containerization**: Docker + docker-compose

---

## Project Structure

```
eveHealthCare/
├── app/
│   ├── api/                    # Route handlers
│   │   ├── auth.py             # Signup, Login
│   │   ├── diagnostics.py      # Centres & Tests CRUD
│   │   ├── bookings.py         # Booking management
│   │   └── payments.py         # Payment & Webhook
│   ├── core/                   # Configuration & utilities
│   │   ├── config.py           # Environment settings
│   │   ├── database.py         # Async engine & session
│   │   ├── security.py         # JWT & password hashing
│   │   └── dependencies.py     # FastAPI dependencies
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── diagnostic.py
│   │   ├── booking.py
│   │   └── payment.py
│   ├── schemas/                # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── diagnostic.py
│   │   ├── booking.py
│   │   ├── payment.py
│   │   └── common.py           # PaginatedResponse generic
│   ├── static/                 # Interactive Web Dashboard
│   │   └── index.html
│   └── main.py                 # FastAPI app entry point (with X-Request-ID middleware)
├── tests/
│   ├── conftest.py             # Fixtures (SQLite-backed)
│   ├── test_auth.py            # Auth & /auth/token form endpoint tests
│   ├── test_diagnostics.py     # Centres & Tests CRUD
│   ├── test_bookings.py        # Booking state machine tests
│   ├── test_payments.py        # Simulated payment, concurrency & webhook tests
│   ├── test_frontend.py        # Frontend route & lint tests
│   ├── test_smoke.py           # E2E & system smoke tests
│   └── lint_frontend.js        # Standalone JS/HTML linter
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

---

## Getting Started

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/abhigyansinhaa/eveHealthCare.git
cd eveHealthCare

# Start both PostgreSQL and the API
docker-compose up --build

# Key URLs:
# Web Dashboard: http://localhost:8000/
# Swagger UI:    http://localhost:8000/docs
# ReDoc:         http://localhost:8000/redoc
```

### Local Setup

**Prerequisites**: Python 3.12+, PostgreSQL running locally

```bash
# Clone and enter the project
git clone https://github.com/abhigyansinhaa/eveHealthCare.git
cd eveHealthCare

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your PostgreSQL credentials

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## API Endpoints

### Health Check
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | ❌ | Service health check |

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/signup` | ❌ | Register a new user |
| `POST` | `/auth/login` | ❌ | Login and get JWT token |

### Diagnostic Centres & Tests
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/centres/` | ✅ | Create a diagnostic centre |
| `GET` | `/centres/` | ❌ | List all centres (paginated) |
| `GET` | `/centres/{id}` | ❌ | Get centre details with tests |
| `POST` | `/centres/{id}/tests` | ✅ | Add a test to a centre |
| `GET` | `/centres/{id}/tests` | ❌ | List tests for a centre (paginated) |

### Bookings
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/bookings/` | ✅ | Book a diagnostic test |
| `GET` | `/bookings/` | ✅ | List your bookings (paginated) |
| `GET` | `/bookings/{id}` | ✅ | Get booking details |
| `POST` | `/bookings/{id}/cancel` | ✅ | Cancel a booking |

### Payments
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/payments/` | ✅ | Initiate simulated payment |
| `POST` | `/payments/webhook/` | ❌ | Payment provider webhook |

---

## Database Schema

```
┌──────────────┐     ┌────────────────────┐     ┌──────────────────┐
│    users      │     │ diagnostic_centres │     │ diagnostic_tests │
├──────────────┤     ├────────────────────┤     ├──────────────────┤
│ id (PK)      │     │ id (PK)            │     │ id (PK)          │
│ email (UQ)   │     │ name               │◄────│ centre_id (FK)   │
│ full_name    │     │ location           │     │ name             │
│ hashed_pass  │     │ description        │     │ description      │
│ is_active    │     │ is_active          │     │ price            │
│ created_at   │     │ created_at         │     │ duration_minutes │
└──────┬───────┘     └────────────────────┘     │ is_active        │
       │                                         │ created_at       │
       │                                         └────────┬─────────┘
       │                                                   │
       │              ┌──────────────┐                     │
       └─────────────►│   bookings   │◄────────────────────┘
                      ├──────────────┤
                      │ id (PK)      │
                      │ user_id (FK) │
                      │ test_id (FK) │
                      │ centre_id(FK)│
                      │ appt_date    │
                      │ amount       │
                      │ status       │  PENDING → CONFIRMED
                      │ created_at   │         → FAILED
                      │ updated_at   │         → CANCELLED
                      └──────┬───────┘
                             │
                      ┌──────┴───────┐
                      │   payments   │
                      ├──────────────┤
                      │ id (PK)      │
                      │ txn_id (UQ)  │ ← Used for webhook idempotency
                      │ booking_id   │ ← One-to-one (UQ)
                      │ amount       │
                      │ status       │  PENDING → SUCCESS / FAILED
                      │ created_at   │
                      │ updated_at   │
                      └──────────────┘
```

**Key constraints:**
- `payments.booking_id` is UNIQUE → only one payment per booking (prevents duplicates)
- `payments.transaction_id` is UNIQUE → used for idempotent webhook processing
- Cascade deletes propagate from parent to child entities

---

## Example Requests

### 1. Sign Up
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "full_name": "Jane Doe",
    "password": "SecureP@ss123"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "password": "SecureP@ss123"
  }'
```

### 3. Create a Diagnostic Centre
```bash
curl -X POST http://localhost:8000/centres/ \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "EVE Diagnostics — South Delhi",
    "location": "123 Health St, New Delhi",
    "description": "Full-service diagnostic centre"
  }'
```

### 4. Add a Test to a Centre
```bash
curl -X POST http://localhost:8000/centres/1/tests \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Complete Blood Count",
    "description": "Full CBC panel",
    "price": 499.99,
    "duration_minutes": 30
  }'
```

### 5. Book a Test
```bash
curl -X POST http://localhost:8000/bookings/ \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "test_id": 1,
    "centre_id": 1,
    "appointment_date": "2026-10-15T10:30:00+05:30"
  }'
```

### 6. Pay for a Booking
```bash
curl -X POST http://localhost:8000/payments/ \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id": 1}'
```

### 7. Webhook (Simulated Payment Provider)

The webhook endpoint requires an `X-Signature` header computed as an HMAC-SHA256 hex digest of the raw JSON body using `WEBHOOK_SECRET`:

```bash
PAYLOAD='{"transaction_id": "<TRANSACTION_ID>", "status": "SUCCESS"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "eve-diagnostic-simulated-webhook-secret-key" | sed 's/^.* //')

curl -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

---

## Running Tests

Tests use an in-memory SQLite database — zero external dependencies needed.

```bash
# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run all 52 tests (Unit, Integration, Smoke, and Frontend lint tests)
pytest -v

# Run frontend lint check standalone
node tests/lint_frontend.js

# Run specific test suites
pytest tests/test_payments.py -v
pytest tests/test_smoke.py -v
pytest tests/test_frontend.py -v

# Run with coverage (if pytest-cov is installed)
pytest --cov=app --cov-report=term-missing
```

---

## Design Decisions & Assumptions

1. **Booking amount snapshot**: The booking amount is derived from the diagnostic test price at creation time, preventing client-side price manipulation.

2. **Row-level locking (`with_for_update`)**:
   - `create_payment` acquires a pessimistic row lock on `Booking` (`SELECT ... FOR UPDATE`) to serialize concurrent payment requests.
   - `payment_webhook` acquires row locks on both `Payment` and `Booking` to serialize incoming webhook events and prevent race conditions.

3. **Concurrent payment protection (409 Conflict)**:
   - Enforced at the database level with a `UNIQUE` constraint on `payments.booking_id`.
   - Simultaneous concurrent payment requests for the same booking are trapped via `IntegrityError` and mapped to `409 Conflict` (e.g. 5 concurrent requests yield 1x `201 Created` and 4x `409 Conflict`).

4. **Failed payments are terminal**:
   - When a payment outcome is `FAILED`, the associated booking transitions to `FAILED`.
   - A failed booking cannot be directly re-paid; the user must create a new booking. This guarantees clear audit trails and prevents financial state corruption.

5. **Webhook idempotency & reconciliation**:
   - The webhook is the reconciliation path for late or out-of-order payment provider events.
   - Terminal payment states (`SUCCESS` and `FAILED`) are immutable and cannot be overwritten.
   - Replaying the same webhook status returns success (`200 OK`) with an idempotent confirmation without mutating the database.

6. **Restricted Webhook Status**:
   - `WebhookPayload.status` strictly accepts `SUCCESS` or `FAILED`. Passing `PENDING` is rejected with `422 Unprocessable Entity`.

7. **HMAC-SHA256 Webhook Verification**:
   - Webhooks are authenticated via the `X-Signature` header calculated from the raw request body and `WEBHOOK_SECRET` using `hmac.compare_digest`.
   - Calls with missing or invalid signatures return `401 Unauthorized`.

8. **OpenAPI / Swagger Authorize Support**:
   - Provides a dedicated form endpoint `POST /auth/token` with `OAuth2PasswordRequestForm` so the Swagger UI "Authorize" modal works interactively out of the box.

9. **Observability & Request Correlation**:
   - Middleware attaches `X-Request-ID` and `X-Process-Time-Ms` headers to every response and outputs structured latency logs.

10. **Test-centre validation**: A booking verifies that the test actually belongs to the specified centre, preventing mismatched bookings.

11. **Isolated SQLite testing**: Tests run against an isolated SQLite instance with table teardown per test for fast, deterministic CI execution.

---

## What I Would Improve

Given more time, I would add:

- **Alembic migrations** — version-controlled schema migrations instead of startup auto-create
- **Redis caching** — cache centre/test listings with TTL-based cache invalidation
- **Celery background jobs** — async notification delivery and external webhook dispatch
- **Rate limiting** — protect auth endpoints against brute-force attacks via token bucket
- **Role-based access control (RBAC)** — distinct admin vs. patient permissions for centre/test management
- **CI/CD pipeline** — GitHub Actions workflow for linting, testing, and Docker builds
- **Soft deletes** — soft archive bookings/payments instead of hard deletes
- **Appointment slot management** — prevent double-booking of specific time slots

