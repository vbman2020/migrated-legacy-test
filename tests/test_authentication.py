"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class TestUserRegistration:
    """Tests for POST /api/users endpoint."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_data: dict):
        """Test successful user registration."""
        response = await client.post("/api/users", json=valid_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == valid_user_data["user"]["email"].lower()
        assert data["user"]["username"] == valid_user_data["user"]["username"].lower()
        assert "token" in data["user"]
        assert "password" not in data["user"]
        assert data["user"]["bio"] is None
        assert data["user"]["image"] is None

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, client: AsyncClient, test_user: User, valid_user_data: dict):
        """Test registration with duplicate email."""
        valid_user_data["user"]["email"] = test_user.email
        response = await client.post("/api/users", json=valid_user_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "email" in data["detail"].lower() or "already" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, client: AsyncClient, test_user: User, valid_user_data: dict):
        """Test registration with duplicate username."""
        valid_user_data["user"]["username"] = test_user.username
        response = await client.post("/api/users", json=valid_user_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "username" in data["detail"].lower() or "already" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_user_invalid_email(self, client: AsyncClient, valid_user_data: dict):
        """Test registration with invalid email format."""
        valid_user_data["user"]["email"] = "invalid-email"
        response = await client.post("/api/users", json=valid_user_data)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_user_short_password(self, client: AsyncClient, valid_user_data: dict):
        """Test registration with password too short."""
        valid_user_data["user"]["password"] = "short"
        response = await client.post("/api/users", json=valid_user_data)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_user_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields."""
        response = await client.post("/api/users", json={"user": {}})
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_user_case_insensitive_email(self, client: AsyncClient, valid_user_data: dict):
        """Test that email is stored in lowercase."""
        valid_user_data["user"]["email"] = "NewUser@EXAMPLE.COM"
        response = await client.post("/api/users", json=valid_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_register_user_xss_prevention(self, client: AsyncClient, valid_user_data: dict):
        """Test XSS prevention in user fields."""
        valid_user_data["user"]["username"] = "<script>alert('xss')</script>"
        response = await client.post("/api/users", json=valid_user_data)
        
        # Should either reject or sanitize
        assert response.status_code in [201, 422]
        if response.status_code == 201:
            data = response.json()
            assert "<script>" not in data["user"]["username"]


class TestUserLogin:
    """Tests for POST /api/users/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User, valid_login_data: dict):
        """Test successful login."""
        response = await client.post("/api/users/login", json=valid_login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == test_user.email
        assert data["user"]["username"] == test_user.username
        assert "token" in data["user"]
        assert "password" not in data["user"]

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, client: AsyncClient, valid_login_data: dict):
        """Test login with non-existent email."""
        valid_login_data["user"]["email"] = "nonexistent@example.com"
        response = await client.post("/api/users/login", json=valid_login_data)
        
        assert response.status_code == 401
        data = response.json()
        # Should not reveal whether email exists
        assert "email or password" in data["detail"].lower() or "invalid credentials" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, valid_login_data: dict):
        """Test login with wrong password."""
        valid_login_data["user"]["password"] = "WrongPassword123!"
        response = await client.post("/api/users/login", json=valid_login_data)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient):
        """Test login with missing fields."""
        response = await client.post("/api/users/login", json={"user": {}})
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_case_insensitive_email(self, client: AsyncClient, test_user: User, valid_login_data: dict):
        """Test login with different email case."""
        valid_login_data["user"]["email"] = test_user.email.upper()
        response = await client.post("/api/users/login", json=valid_login_data)
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db_session: AsyncSession, test_user: User, valid_login_data: dict):
        """Test login with inactive account."""
        test_user.is_active = False
        await db_session.commit()
        
        response = await client.post("/api/users/login", json=valid_login_data)
        
        assert response.status_code == 401


class TestGetCurrentUser:
    """Tests for GET /api/user endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test getting current user with valid token."""
        response = await client.get("/api/user", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == test_user.email
        assert data["user"]["username"] == test_user.username
        assert "token" in data["user"]

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without token."""
        response = await client.get("/api/user")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        response = await client.get(
            "/api/user",
            headers={"Authorization": "Token invalid-token-here"}
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_header(self, client: AsyncClient, auth_token: str):
        """Test with malformed authorization header."""
        response = await client.get(
            "/api/user",
            headers={"Authorization": f"Bearer {auth_token}"}  # Wrong scheme
        )
        
        assert response.status_code == 401


class TestUpdateUser:
    """Tests for PUT /api/user endpoint."""

    @pytest.mark.asyncio
    async def test_update_user_email(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating user email."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"email": "newemail@example.com"}}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "newemail@example.com"

    @pytest.mark.asyncio
    async def test_update_user_username(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating username."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"username": "newusername"}}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "newusername"

    @pytest.mark.asyncio
    async def test_update_user_bio(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating user bio."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"bio": "This is my new bio"}}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["bio"] == "This is my new bio"

    @pytest.mark.asyncio
    async def test_update_user_image(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating user image URL."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"image": "https://example.com/avatar.jpg"}}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["image"] == "https://example.com/avatar.jpg"

    @pytest.mark.asyncio
    async def test_update_user_password(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating user password."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"password": "NewPassword123!@#"}}
        )
        
        assert response.status_code == 200
        
        # Verify can login with new password
        login_response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": test_user.email,
                    "password": "NewPassword123!@#"
                }
            }
        )
        assert login_response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_user_duplicate_email(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test updating to an email that's already taken."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"email": test_user2.email}}
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_user_duplicate_username(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test updating to a username that's already taken."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"username": test_user2.username}}
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_user_no_auth(self, client: AsyncClient):
        """Test updating user without authentication."""
        response = await client.put(
            "/api/user",
            json={"user": {"bio": "New bio"}}
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_user_xss_prevention_bio(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test XSS prevention in bio field."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"bio": "<script>alert('xss')</script>"}}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Bio should be sanitized
        assert "<script>" not in data["user"]["bio"]

    @pytest.mark.asyncio
    async def test_update_user_invalid_image_url(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating with invalid image URL."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"image": "not-a-valid-url"}}
        )
        
        # Should either accept any string or validate URL
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_update_user_multiple_fields(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating multiple fields at once."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "email": "updated@example.com",
                    "username": "updateduser",
                    "bio": "Updated bio",
                    "image": "https://example.com/new-avatar.jpg"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "updated@example.com"
        assert data["user"]["username"] == "updateduser"
        assert data["user"]["bio"] == "Updated bio"
        assert data["user"]["image"] == "https://example.com/new-avatar.jpg"
