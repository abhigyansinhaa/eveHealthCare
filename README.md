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
| Unit & Integration Tests (37 tests) | ✅ |
| Pagination | ✅ |

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
│   └── main.py                 # FastAPI app entry point
├── tests/
│   ├── conftest.py             # Fixtures (SQLite-backed)
│   ├── test_auth.py
│   ├── test_diagnostics.py
│   ├── test_bookings.py
│   └── test_payments.py
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
```bash
curl -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "<TRANSACTION_ID>",
    "status": "SUCCESS"
  }'
```

---

## Running Tests

Tests use an in-memory SQLite database — no PostgreSQL needed.

```bash
# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run all tests
pytest -v

# Run specific test file
pytest tests/test_auth.py -v

# Run with coverage (if pytest-cov is installed)
pytest --cov=app --cov-report=term-missing
```

---

## Design Decisions & Assumptions

1. **Booking amount is derived from test price** at creation time, not user-supplied. This prevents price manipulation.

2. **Webhook is unauthenticated** — real payment webhooks are server-to-server calls authenticated via signatures. We keep the endpoint open for simplicity but note this in the docs.

3. **One payment per booking** — enforced at the database level with a UNIQUE constraint on `payments.booking_id`. Prevents duplicate payments even under race conditions.

4. **Idempotent webhook** — replaying the same webhook event:
   - Same status → returns success without changes
   - Terminal state (SUCCESS/FAILED) → cannot be overridden

5. **Booking state machine**: Only PENDING bookings can be cancelled or paid. Once CONFIRMED/FAILED/CANCELLED, the state is terminal.

6. **Test-centre validation**: A booking verifies that the test actually belongs to the specified centre, preventing mismatched bookings.

7. **Tests use SQLite** for speed and zero-dependency CI. The async ORM layer ensures compatibility.

8. **Auto-create tables on startup** via the lifespan handler. In production, this would be replaced with Alembic migrations.

---

## What I Would Improve

Given more time, I would add:

- **Alembic migrations** — version-controlled schema changes instead of auto-create
- **Redis caching** — cache centre/test listings with TTL-based invalidation
- **Celery background jobs** — async payment processing, email notifications
- **Rate limiting** — protect auth endpoints from brute-force attacks
- **Webhook signature verification** — HMAC-based authentication for webhooks
- **Role-based access control** — admin vs. patient roles for centre/test management
- **Structured logging** — JSON logging with correlation IDs for tracing
- **CI/CD pipeline** — GitHub Actions for lint, test, build, deploy
- **Soft deletes** — archive bookings/payments instead of hard deletes
- **Appointment slot management** — prevent double-booking of time slots
