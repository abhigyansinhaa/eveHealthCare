"""
Tests for authentication endpoints — signup and login.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSignup:

    async def test_signup_success(self, client: AsyncClient):
        response = await client.post("/auth/signup", json={
            "email": "newuser@example.com",
            "full_name": "New User",
            "password": "StrongPass123",
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["full_name"] == "New User"

    async def test_signup_duplicate_email(self, client: AsyncClient):
        # First signup
        await client.post("/auth/signup", json={
            "email": "dup@example.com",
            "full_name": "User One",
            "password": "StrongPass123",
        })
        # Duplicate
        response = await client.post("/auth/signup", json={
            "email": "dup@example.com",
            "full_name": "User Two",
            "password": "AnotherPass123",
        })
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    async def test_signup_invalid_email(self, client: AsyncClient):
        response = await client.post("/auth/signup", json={
            "email": "not-an-email",
            "full_name": "Bad Email",
            "password": "StrongPass123",
        })
        assert response.status_code == 422

    async def test_signup_short_password(self, client: AsyncClient):
        response = await client.post("/auth/signup", json={
            "email": "short@example.com",
            "full_name": "Short Pass",
            "password": "123",
        })
        assert response.status_code == 422

    async def test_signup_missing_fields(self, client: AsyncClient):
        response = await client.post("/auth/signup", json={})
        assert response.status_code == 422


@pytest.mark.asyncio
class TestLogin:

    async def test_login_success(self, client: AsyncClient):
        # Signup first
        await client.post("/auth/signup", json={
            "email": "login@example.com",
            "full_name": "Login User",
            "password": "StrongPass123",
        })
        # Login
        response = await client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "StrongPass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "login@example.com"

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/auth/signup", json={
            "email": "wrongpass@example.com",
            "full_name": "Wrong Pass",
            "password": "StrongPass123",
        })
        response = await client.post("/auth/login", json={
            "email": "wrongpass@example.com",
            "password": "WrongPassword",
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        response = await client.post("/auth/login", json={
            "email": "noone@example.com",
            "password": "StrongPass123",
        })
        assert response.status_code == 401
