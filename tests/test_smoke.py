"""
Smoke tests for EVE Healthcare backend service.
Validates service health, OpenAPI specification, interactive docs, and end-to-end user flows.
"""

from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient

from app.core.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
class TestBackendSmoke:
    """Smoke test suite validating critical system paths and endpoints."""

    async def test_health_check_smoke(self, client: AsyncClient):
        """Smoke test: Health check endpoint responds with service details."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == settings.APP_NAME
        assert data["version"] == settings.APP_VERSION

    async def test_openapi_and_docs_smoke(self, client: AsyncClient):
        """Smoke test: OpenAPI schema and documentation pages render properly."""
        # 1. OpenAPI schema
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "/health" in schema["paths"]
        assert "/auth/signup" in schema["paths"]
        assert "/auth/login" in schema["paths"]
        assert "/centres/" in schema["paths"]
        assert "/bookings/" in schema["paths"]
        assert "/payments/" in schema["paths"]
        assert "/payments/webhook/" in schema["paths"]

        # 2. Swagger UI
        docs_res = await client.get("/docs")
        assert docs_res.status_code == 200
        assert "swagger" in docs_res.text.lower() or "html" in docs_res.headers["content-type"]

        # 3. Redoc
        redoc_res = await client.get("/redoc")
        assert redoc_res.status_code == 200
        assert "redoc" in redoc_res.text.lower() or "html" in redoc_res.headers["content-type"]

    async def test_e2e_booking_payment_lifecycle_smoke(self, client: AsyncClient):
        """
        Comprehensive smoke test:
        Signup -> Login -> Create Centre -> Add Test -> Create Booking ->
        Initiate Payment -> Trigger Webhook -> Confirm Booking & Payment.
        """
        # 1. User Signup
        signup_res = await client.post("/auth/signup", json={
            "email": "smoke_tester@evehealth.com",
            "full_name": "Smoke Tester",
            "password": "SmokeTestSecurePass123",
        })
        assert signup_res.status_code == 201
        token = signup_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 2. User Login
        login_res = await client.post("/auth/login", json={
            "email": "smoke_tester@evehealth.com",
            "password": "SmokeTestSecurePass123",
        })
        assert login_res.status_code == 200
        assert login_res.json()["access_token"] is not None

        # 3. Create Diagnostic Centre
        centre_res = await client.post("/centres/", json={
            "name": "Smoke Diagnostic Centre",
            "location": "Sector 62, Noida",
            "description": "High-tech test centre for smoke checks",
            "contact_phone": "+91-9999888877",
            "contact_email": "noida@evehealth.com",
        }, headers=auth_headers)
        assert centre_res.status_code == 201
        centre_id = centre_res.json()["id"]

        # 4. Add Diagnostic Test to Centre
        test_res = await client.post(f"/centres/{centre_id}/tests", json={
            "name": "Comprehensive Metabolic Panel (CMP)",
            "description": "Tests organ health and electrolytes",
            "price": 799.50,
            "duration_minutes": 45,
        }, headers=auth_headers)
        assert test_res.status_code == 201
        test_id = test_res.json()["id"]

        # 5. Create Booking
        future_slot = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        booking_res = await client.post("/bookings/", json={
            "centre_id": centre_id,
            "test_id": test_id,
            "appointment_date": future_slot,
        }, headers=auth_headers)
        assert booking_res.status_code == 201
        booking_data = booking_res.json()
        booking_id = booking_data["id"]
        assert booking_data["status"] == "PENDING"
        assert booking_data["amount"] == 799.50

        # 6. Initiate Payment
        payment_res = await client.post("/payments/", json={
            "booking_id": booking_id,
        }, headers=auth_headers)
        assert payment_res.status_code == 201
        payment_data = payment_res.json()
        txn_id = payment_data["transaction_id"]
        assert payment_data["status"] in ["SUCCESS", "FAILED"]

        # 7. Check Booking State matches simulated payment
        booking_check = await client.get(f"/bookings/{booking_id}", headers=auth_headers)
        assert booking_check.status_code == 200
        expected_booking_status = "CONFIRMED" if payment_data["status"] == "SUCCESS" else "CANCELLED"
        assert booking_check.json()["status"] == expected_booking_status

        # 8. Webhook Processing & Idempotency
        webhook_res = await client.post("/payments/webhook/", json={
            "transaction_id": txn_id,
            "status": payment_data["status"],
        })
        assert webhook_res.status_code == 200
        webhook_data = webhook_res.json()
        assert webhook_data["transaction_id"] == txn_id
        assert webhook_data["payment_status"] == payment_data["status"]
