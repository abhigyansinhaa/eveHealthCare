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
