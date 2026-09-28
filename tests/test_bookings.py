"""
Tests for booking endpoints.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestBookings:

    async def test_create_booking_success(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        response = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "PENDING"
        assert data["test_id"] == sample_test["id"]
        assert data["centre_id"] == sample_centre["id"]
        assert data["amount"] == sample_test["price"]

    async def test_create_booking_past_date(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        response = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": past_date,
        })
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    async def test_create_booking_invalid_test_at_centre(
        self, authenticated_client: AsyncClient, sample_centre: dict
    ):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        response = await authenticated_client.post("/bookings/", json={
            "test_id": 99999,
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        assert response.status_code == 404

    async def test_create_booking_unauthenticated(self, client: AsyncClient):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        response = await client.post("/bookings/", json={
            "test_id": 1,
            "centre_id": 1,
            "appointment_date": future_date,
        })
        assert response.status_code == 401

    async def test_list_bookings(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        # Create a booking first
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })

        response = await authenticated_client.get("/bookings/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_get_booking(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        response = await authenticated_client.get(f"/bookings/{booking_id}")
        assert response.status_code == 200
        assert response.json()["id"] == booking_id

    async def test_get_booking_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/bookings/99999")
        assert response.status_code == 404

    async def test_cancel_booking(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        response = await authenticated_client.post(f"/bookings/{booking_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    async def test_cancel_already_cancelled(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        # Cancel once
        await authenticated_client.post(f"/bookings/{booking_id}/cancel")
        # Try again
        response = await authenticated_client.post(f"/bookings/{booking_id}/cancel")
        assert response.status_code == 400

    async def test_access_other_users_booking(
        self, client: AsyncClient, authenticated_client: AsyncClient,
        sample_centre: dict, sample_test: dict
    ):
        """A different authenticated user should not see another user's booking."""
        # Create booking with user 1
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        # Signup as a different user
        signup_resp = await client.post("/auth/signup", json={
            "email": "other@example.com",
            "full_name": "Other User",
            "password": "OtherPass123",
        })
        other_token = signup_resp.json()["access_token"]

        # Try to access user 1's booking
        response = await client.get(
            f"/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 403

    async def test_create_booking_nonexistent_centre(
        self, authenticated_client: AsyncClient, sample_test: dict
    ):
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        response = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": 99999,
            "appointment_date": future_date,
        })
        assert response.status_code == 404
        assert "centre with id 99999 not found" in response.json()["detail"].lower()

    async def test_cancel_booking_forbidden_other_user(
        self, client: AsyncClient, authenticated_client: AsyncClient,
        sample_centre: dict, sample_test: dict
    ):
        """A user cannot cancel another user's booking."""
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        signup_resp = await client.post("/auth/signup", json={
            "email": "intruder@example.com",
            "full_name": "Intruder User",
            "password": "IntruderPass123",
        })
        intruder_token = signup_resp.json()["access_token"]

        response = await client.post(
            f"/bookings/{booking_id}/cancel",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    async def test_cancel_confirmed_booking_fails(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """A confirmed (paid) booking cannot be cancelled."""
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        pay_resp = await authenticated_client.post("/payments/", json={"booking_id": booking_id})
        assert pay_resp.status_code == 201
        assert pay_resp.json()["status"] == "SUCCESS"

        cancel_resp = await authenticated_client.post(f"/bookings/{booking_id}/cancel")
        assert cancel_resp.status_code == 400
        assert "cannot cancel a booking with status 'confirmed'" in cancel_resp.json()["detail"].lower()

    async def test_list_bookings_status_filter(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        """Filtering by ?status= returns only matching bookings."""
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        # Booking 1: will stay PENDING
        b1 = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        b1_id = b1.json()["id"]

        # Booking 2: will be CANCELLED
        b2 = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        b2_id = b2.json()["id"]
        await authenticated_client.post(f"/bookings/{b2_id}/cancel")

        # Query pending
        res_pending = await authenticated_client.get("/bookings/?status=PENDING")
        assert res_pending.status_code == 200
        pending_ids = [item["id"] for item in res_pending.json()["items"]]
        assert b1_id in pending_ids
        assert b2_id not in pending_ids

        # Query cancelled
        res_cancelled = await authenticated_client.get("/bookings/?status=CANCELLED")
        assert res_cancelled.status_code == 200
        cancelled_ids = [item["id"] for item in res_cancelled.json()["items"]]
        assert b2_id in cancelled_ids
        assert b1_id not in cancelled_ids

    async def test_get_booking_payment_flow(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict, monkeypatch
    ):
        """GET /bookings/{id}/payment returns payment details or 404 if unpaid."""
        monkeypatch.setattr("app.api.payments.random.random", lambda: 0.1)
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = await authenticated_client.post("/bookings/", json={
            "test_id": sample_test["id"],
            "centre_id": sample_centre["id"],
            "appointment_date": future_date,
        })
        booking_id = create_resp.json()["id"]

        # Unpaid check -> 404
        check_before = await authenticated_client.get(f"/bookings/{booking_id}/payment")
        assert check_before.status_code == 404
        assert "no payment found" in check_before.json()["detail"].lower()

        # Pay
        await authenticated_client.post("/payments/", json={"booking_id": booking_id})

        # Paid check -> 200
        check_after = await authenticated_client.get(f"/bookings/{booking_id}/payment")
        assert check_after.status_code == 200
        assert check_after.json()["booking_id"] == booking_id
        assert check_after.json()["status"] == "SUCCESS"
