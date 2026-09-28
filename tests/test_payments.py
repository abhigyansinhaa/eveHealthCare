"""
Tests for payment and webhook endpoints.
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import get_settings
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from tests.conftest import TestSessionLocal

settings = get_settings()


def sign_webhook_payload(payload: dict) -> tuple[bytes, dict]:
    """Helper: serialize payload and generate HMAC-SHA256 signature headers."""
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    headers = {"X-Signature": sig, "Content-Type": "application/json"}
    return raw, headers


@pytest.mark.asyncio
class TestPayments:

    async def _create_booking(
        self, client: AsyncClient, centre_id: int, test_id: int
    ) -> dict:
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        response = await client.post("/bookings/", json={
            "test_id": test_id,
            "centre_id": centre_id,
            "appointment_date": future_date,
        })
        assert response.status_code == 201
        return response.json()

    async def test_create_payment(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        # Force deterministic SUCCESS outcome
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)

        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        response = await authenticated_client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["booking_id"] == booking["id"]
        assert data["status"] == "SUCCESS"
        assert "transaction_id" in data

    async def test_payment_duplicate_prevented(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        # First payment
        res1 = await authenticated_client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        assert res1.status_code == 201

        # Second payment attempt returns 409 Conflict
        response = await authenticated_client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_concurrent_payments_prevented(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        """Simulate simultaneous concurrent payments for a single booking."""
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )

        async def attempt_payment():
            return await authenticated_client.post("/payments/", json={
                "booking_id": booking["id"],
            })

        # Launch 5 simultaneous requests
        responses = await asyncio.gather(*(attempt_payment() for _ in range(5)))
        status_codes = [r.status_code for r in responses]

        # Exactly one must succeed with 201, and the others must return 409 Conflict
        assert status_codes.count(201) == 1
        assert status_codes.count(409) == 4

    async def test_payment_invalid_booking(self, authenticated_client: AsyncClient):
        response = await authenticated_client.post("/payments/", json={
            "booking_id": 99999,
        })
        assert response.status_code == 404

    async def test_payment_unauthenticated(self, client: AsyncClient):
        response = await client.post("/payments/", json={
            "booking_id": 1,
        })
        assert response.status_code == 401

    async def test_get_payment_success(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """User can retrieve their own payment details by ID."""
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        pay_res = await authenticated_client.post("/payments/", json={"booking_id": booking["id"]})
        assert pay_res.status_code == 201
        payment_id = pay_res.json()["id"]

        get_res = await authenticated_client.get(f"/payments/{payment_id}")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["id"] == payment_id
        assert data["booking_id"] == booking["id"]
        assert data["status"] == "SUCCESS"

    async def test_get_payment_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/payments/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_payment_forbidden_other_user(
        self, client: AsyncClient, authenticated_client: AsyncClient,
        sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """User B cannot view User A's payment."""
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        pay_res = await authenticated_client.post("/payments/", json={"booking_id": booking["id"]})
        payment_id = pay_res.json()["id"]

        # User B registers
        b_signup = await client.post("/auth/signup", json={
            "email": "userb@example.com",
            "full_name": "User B",
            "password": "Password123",
        })
        b_token = b_signup.json()["access_token"]

        response = await client.get(
            f"/payments/{payment_id}",
            headers={"Authorization": f"Bearer {b_token}"},
        )
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    async def test_payment_forbidden_other_users_booking(
        self, client: AsyncClient, authenticated_client: AsyncClient,
        sample_centre: dict, sample_test: dict
    ):
        """User B cannot pay for User A's booking."""
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )

        b_signup = await client.post("/auth/signup", json={
            "email": "intruder_pay@example.com",
            "full_name": "Intruder P",
            "password": "Password123",
        })
        b_token = b_signup.json()["access_token"]

        response = await client.post(
            "/payments/",
            json={"booking_id": booking["id"]},
            headers={"Authorization": f"Bearer {b_token}"},
        )
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    async def test_payment_cancelled_booking_fails(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        """Cannot pay for a booking that has been cancelled."""
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        # Cancel booking
        await authenticated_client.post(f"/bookings/{booking['id']}/cancel")

        # Attempt payment
        response = await authenticated_client.post("/payments/", json={"booking_id": booking["id"]})
        assert response.status_code == 400
        assert "cannot process payment for a booking with status 'cancelled'" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestWebhook:

    async def _setup_payment(
        self, client: AsyncClient, centre_id: int, test_id: int, monkeypatch=None
    ) -> dict:
        """Helper: create booking + payment, return payment data."""
        if monkeypatch:
            monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)

        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        booking_resp = await client.post("/bookings/", json={
            "test_id": test_id,
            "centre_id": centre_id,
            "appointment_date": future_date,
        })
        booking = booking_resp.json()
        payment_resp = await client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        assert payment_resp.status_code == 201
        return payment_resp.json()

    async def test_webhook_missing_signature(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Calls without X-Signature header must be rejected with 401."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"], monkeypatch
        )
        response = await authenticated_client.post("/payments/webhook/", json={
            "transaction_id": payment["transaction_id"],
            "status": "SUCCESS",
        })
        assert response.status_code == 401
        assert "missing x-signature" in response.json()["detail"].lower()

    async def test_webhook_invalid_signature(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Calls with invalid X-Signature header must be rejected with 401."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"], monkeypatch
        )
        response = await authenticated_client.post(
            "/payments/webhook/",
            json={"transaction_id": payment["transaction_id"], "status": "SUCCESS"},
            headers={"X-Signature": "invalid_hex_signature"},
        )
        assert response.status_code == 401
        assert "invalid webhook signature" in response.json()["detail"].lower()

    async def test_webhook_rejects_pending_status(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Webhook should reject status PENDING with a 422 Unprocessable Entity."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"], monkeypatch
        )
        raw_body, headers = sign_webhook_payload({
            "transaction_id": payment["transaction_id"],
            "status": "PENDING",
        })
        response = await authenticated_client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 422

    async def test_webhook_idempotent(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Sending the same webhook multiple times should not corrupt state."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"], monkeypatch
        )

        payload = {
            "transaction_id": payment["transaction_id"],
            "status": payment["status"],
        }
        raw_body, headers = sign_webhook_payload(payload)

        # First call
        response1 = await authenticated_client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response1.status_code == 200
        assert "already processed" in response1.json()["message"].lower()

        # Replayed webhook call
        response2 = await authenticated_client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response2.status_code == 200
        assert response2.json()["payment_status"] == payment["status"]

    async def test_webhook_invalid_transaction(self, client: AsyncClient):
        raw_body, headers = sign_webhook_payload({
            "transaction_id": "nonexistent-txn-id",
            "status": "SUCCESS",
        })
        response = await client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 404

    async def test_webhook_terminal_state_protection(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Once a payment reaches SUCCESS or FAILED, it cannot be overridden."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"], monkeypatch
        )
        # Try to override terminal status
        opposite_status = "FAILED" if payment["status"] == "SUCCESS" else "SUCCESS"
        raw_body, headers = sign_webhook_payload({
            "transaction_id": payment["transaction_id"],
            "status": opposite_status,
        })
        response = await authenticated_client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 200
        assert "terminal state" in response.json()["message"].lower()
        # Original status is preserved
        assert response.json()["payment_status"] == payment["status"]

    async def test_webhook_apply_update_branch(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Force a payment to PENDING in the DB and verify webhook reconciles it to SUCCESS/CONFIRMED."""
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)
        # 1. Create booking and payment
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        booking_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking = booking_resp.json()
        pay_res = await authenticated_client.post("/payments/", json={"booking_id": booking["id"]})
        assert pay_res.status_code == 201
        txn_id = pay_res.json()["transaction_id"]

        # 2. Reset payment & booking to PENDING via DB session to simulate pending state
        async with TestSessionLocal() as session:
            await session.execute(
                update(Payment).where(Payment.transaction_id == txn_id).values(status=PaymentStatus.PENDING)
            )
            await session.execute(
                update(Booking).where(Booking.id == booking["id"]).values(status=BookingStatus.PENDING)
            )
            await session.commit()

        # 3. Call webhook with SUCCESS
        raw_body, headers = sign_webhook_payload({
            "transaction_id": txn_id,
            "status": "SUCCESS",
        })
        response = await authenticated_client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Payment status updated successfully."
        assert data["payment_status"] == "SUCCESS"
        assert data["booking_status"] == "CONFIRMED"

        # 4. Verify booking is confirmed via GET /bookings/{id}
        booking_check = await authenticated_client.get(f"/bookings/{booking['id']}")
        assert booking_check.status_code == 200
        assert booking_check.json()["status"] == "CONFIRMED"

    async def test_webhook_apply_update_failed_branch(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """Force a payment to PENDING and verify webhook reconciles it to FAILED."""
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        booking_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking = booking_resp.json()
        pay_res = await authenticated_client.post("/payments/", json={"booking_id": booking["id"]})
        assert pay_res.status_code == 201
        txn_id = pay_res.json()["transaction_id"]

        async with TestSessionLocal() as session:
            await session.execute(
                update(Payment).where(Payment.transaction_id == txn_id).values(status=PaymentStatus.PENDING)
            )
            await session.execute(
                update(Booking).where(Booking.id == booking["id"]).values(status=BookingStatus.PENDING)
            )
            await session.commit()

        raw_body, headers = sign_webhook_payload({
            "transaction_id": txn_id,
            "status": "FAILED",
        })
        response = await authenticated_client.post(
            "/payments/webhook/",
            content=raw_body,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Payment status updated successfully."
        assert data["payment_status"] == "FAILED"
        assert data["booking_status"] == "FAILED"

        booking_check = await authenticated_client.get(f"/bookings/{booking['id']}")
        assert booking_check.status_code == 200
        assert booking_check.json()["status"] == "FAILED"
