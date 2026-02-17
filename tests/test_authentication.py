"""Tests for authentication endpoints.

Tests registration, login, get current user, and update user.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import AuthService


class TestUserRegistration:
    """Test user registration endpoint POST /api/users."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "test@example.com",
                    "username": "testuser",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["username"] == "testuser"
        assert "token" in data["user"]
        assert "password" not in data["user"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "test@example.com",
                    "username": "newuser",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert "email" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate username fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "newemail@example.com",
                    "username": "testuser",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert "username" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "not-an-email",
                    "username": "testuser",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """Test registration with weak password fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "test@example.com",
                    "username": "testuser",
                    "password": "weak",
                }
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username(self, client: AsyncClient):
        """Test registration with invalid username characters fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "test@example.com",
                    "username": "test user!",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "test@example.com",
                }
            },
        )
        assert response.status_code == 422


class TestUserLogin:
    """Test user login endpoint POST /api/users/login."""

    @pytest.mark.asyncio
    async def test_login_success_with_email(self, client: AsyncClient, test_user: User):
        """Test successful login with email."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["username"] == "testuser"
        assert "token" in data["user"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password fails."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "WrongPass123!",
                }
            },
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "nonexistent@example.com",
                    "password": "TestPass123!",
                }
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient):
        """Test login with missing fields fails."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                }
            },
        )
        assert response.status_code == 422


class TestGetCurrentUser:
    """Test get current user endpoint GET /api/user."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, auth_headers: dict):
        """Test getting current user with valid token."""
        response = await client.get("/api/user", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["username"] == "testuser"
        assert "token" in data["user"]

    @pytest.mark.asyncio
    async def test_get_current_user_no_auth(self, client: AsyncClient):
        """Test getting current user without auth token fails."""
        response = await client.get("/api/user")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token fails."""
        response = await client.get(
            "/api/user",
            headers={"Authorization": "Token invalid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_wrong_format(self, client: AsyncClient):
        """Test getting current user with wrong auth header format fails."""
        response = await client.get(
            "/api/user",
            headers={"Authorization": "Bearer some-token"},
        )
        assert response.status_code == 401


class TestUpdateUser:
    """Test update user endpoint PUT /api/user."""

    @pytest.mark.asyncio
    async def test_update_user_email(self, client: AsyncClient, auth_headers: dict):
        """Test updating user email."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "email": "newemail@example.com",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "newemail@example.com"

    @pytest.mark.asyncio
    async def test_update_user_bio_image(self, client: AsyncClient, auth_headers: dict):
        """Test updating user bio and image."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "bio": "I like coding",
                    "image": "https://example.com/avatar.jpg",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["bio"] == "I like coding"
        assert data["user"]["image"] == "https://example.com/avatar.jpg"

    @pytest.mark.asyncio
    async def test_update_user_password(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """Test updating user password."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "password": "NewPass123!",
                }
            },
        )
        assert response.status_code == 200
        
        # Verify can login with new password
        login_response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "NewPass123!",
                }
            },
        )
        assert login_response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_user_duplicate_email(self, client: AsyncClient, auth_headers: dict, test_user2: User):
        """Test updating to duplicate email fails."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "email": "test2@example.com",
                }
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_user_invalid_email(self, client: AsyncClient, auth_headers: dict):
        """Test updating with invalid email fails."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "email": "not-an-email",
                }
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_user_no_auth(self, client: AsyncClient):
        """Test updating user without auth fails."""
        response = await client.put(
            "/api/user",
            json={
                "user": {
                    "email": "newemail@example.com",
                }
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_user_empty_body(self, client: AsyncClient, auth_headers: dict):
        """Test updating user with empty update succeeds (returns current user)."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "test@example.com"
