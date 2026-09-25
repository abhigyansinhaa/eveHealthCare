"""
Tests for payment and webhook endpoints.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


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
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        response = await authenticated_client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["booking_id"] == booking["id"]
        assert data["status"] in ("SUCCESS", "FAILED")
        assert "transaction_id" in data

    async def test_payment_duplicate_prevented(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        booking = await self._create_booking(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )
        # First payment
        await authenticated_client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        # Second payment attempt
        response = await authenticated_client.post("/payments/", json={
            "booking_id": booking["id"],
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

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


@pytest.mark.asyncio
class TestWebhook:

    async def _setup_payment(
        self, client: AsyncClient, centre_id: int, test_id: int
    ) -> dict:
        """Helper: create booking + payment, return payment data."""
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
        return payment_resp.json()

    async def test_webhook_idempotent(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        """Sending the same webhook multiple times should not corrupt state."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )

        # Send the same status again (idempotency test)
        response1 = await authenticated_client.post("/payments/webhook/", json={
            "transaction_id": payment["transaction_id"],
            "status": payment["status"],
        })
        assert response1.status_code == 200

        # Send it a second time — should still be fine
        response2 = await authenticated_client.post("/payments/webhook/", json={
            "transaction_id": payment["transaction_id"],
            "status": payment["status"],
        })
        assert response2.status_code == 200
        assert response2.json()["payment_status"] == payment["status"]

    async def test_webhook_invalid_transaction(self, client: AsyncClient):
        response = await client.post("/payments/webhook/", json={
            "transaction_id": "nonexistent-txn-id",
            "status": "SUCCESS",
        })
        assert response.status_code == 404

    async def test_webhook_terminal_state_protection(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        """Once a payment reaches SUCCESS or FAILED, it should not change."""
        payment = await self._setup_payment(
            authenticated_client, sample_centre["id"], sample_test["id"]
        )

        # Payment is already in a terminal state (SUCCESS or FAILED from simulation)
        # Try to override with opposite status
        opposite_status = "FAILED" if payment["status"] == "SUCCESS" else "SUCCESS"
        response = await authenticated_client.post("/payments/webhook/", json={
            "transaction_id": payment["transaction_id"],
            "status": opposite_status,
        })
        assert response.status_code == 200
        # The original status should be preserved
        assert response.json()["payment_status"] == payment["status"]
