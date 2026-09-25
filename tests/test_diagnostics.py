"""
Tests for diagnostic centres and tests endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestDiagnosticCentres:

    async def test_create_centre_authenticated(self, authenticated_client: AsyncClient):
        response = await authenticated_client.post("/centres/", json={
            "name": "Test Centre Alpha",
            "location": "456 Lab Ave, Delhi",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Centre Alpha"
        assert data["location"] == "456 Lab Ave, Delhi"
        assert data["is_active"] is True

    async def test_create_centre_unauthenticated(self, client: AsyncClient):
        response = await client.post("/centres/", json={
            "name": "Unauthorized Centre",
            "location": "Nowhere",
        })
        assert response.status_code == 401

    async def test_list_centres(self, authenticated_client: AsyncClient, sample_centre: dict):
        response = await authenticated_client.get("/centres/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["page"] == 1

    async def test_list_centres_pagination(self, authenticated_client: AsyncClient):
        # Create multiple centres
        for i in range(5):
            await authenticated_client.post("/centres/", json={
                "name": f"Centre {i}",
                "location": f"Location {i}",
            })

        response = await authenticated_client.get("/centres/?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["page_size"] == 2

    async def test_get_centre_detail(self, authenticated_client: AsyncClient, sample_centre: dict):
        centre_id = sample_centre["id"]
        response = await authenticated_client.get(f"/centres/{centre_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == centre_id
        assert "tests" in data

    async def test_get_centre_not_found(self, client: AsyncClient):
        response = await client.get("/centres/99999")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestDiagnosticTests:

    async def test_create_test(self, authenticated_client: AsyncClient, sample_centre: dict):
        centre_id = sample_centre["id"]
        response = await authenticated_client.post(f"/centres/{centre_id}/tests", json={
            "name": "Lipid Panel",
            "description": "Cholesterol and triglycerides",
            "price": 799.50,
            "duration_minutes": 45,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Lipid Panel"
        assert data["price"] == 799.50
        assert data["centre_id"] == centre_id

    async def test_create_test_invalid_centre(self, authenticated_client: AsyncClient):
        response = await authenticated_client.post("/centres/99999/tests", json={
            "name": "Orphan Test",
            "price": 100.00,
        })
        assert response.status_code == 404

    async def test_create_test_invalid_price(self, authenticated_client: AsyncClient, sample_centre: dict):
        centre_id = sample_centre["id"]
        response = await authenticated_client.post(f"/centres/{centre_id}/tests", json={
            "name": "Free Test",
            "price": -10,
        })
        assert response.status_code == 422

    async def test_list_tests_for_centre(
        self, authenticated_client: AsyncClient, sample_centre: dict, sample_test: dict
    ):
        centre_id = sample_centre["id"]
        response = await authenticated_client.get(f"/centres/{centre_id}/tests")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
