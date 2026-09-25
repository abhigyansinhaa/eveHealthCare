import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestFrontendDashboard:
    async def test_root_serves_html(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "EVE HealthCare" in response.text
        assert "Diagnostic Portal" in response.text

    async def test_dashboard_serves_html(self, client: AsyncClient):
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "EVE HealthCare" in response.text
