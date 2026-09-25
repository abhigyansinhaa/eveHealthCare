"""
Test configuration — async fixtures using SQLite for isolated, fast tests.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.main import app


# Use in-memory SQLite for tests (fast, no external deps)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """A client that is already authenticated (signed up)."""
    response = await client.post("/auth/signup", json={
        "email": "testuser@example.com",
        "full_name": "Test User",
        "password": "SecureP@ss123",
    })
    assert response.status_code == 201
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def sample_centre(authenticated_client: AsyncClient) -> dict:
    """Create a sample diagnostic centre and return its data."""
    response = await authenticated_client.post("/centres/", json={
        "name": "EVE Diagnostics — Test Centre",
        "location": "123 Health Street, Test City",
        "description": "A test diagnostic centre.",
    })
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def sample_test(authenticated_client: AsyncClient, sample_centre: dict) -> dict:
    """Create a sample diagnostic test and return its data."""
    centre_id = sample_centre["id"]
    response = await authenticated_client.post(f"/centres/{centre_id}/tests", json={
        "name": "Complete Blood Count",
        "description": "Full CBC panel",
        "price": 499.99,
        "duration_minutes": 30,
    })
    assert response.status_code == 201
    return response.json()
