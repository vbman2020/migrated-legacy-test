"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.profiles.models import Profile


class TestUserRegistration:
    """Tests for POST /api/users (user registration)."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful user registration."""
        payload = {
            "user": {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123!"
            }
        }
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "newuser@example.com"
        assert "token" in data["user"]
        assert "password" not in data["user"]
        
        # Verify user was created in database
        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "newuser@example.com"
        
        # Verify profile was created
        assert user.profile is not None

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate username."""
        payload = {
            "user": {
                "username": "testuser",  # Already exists
                "email": "different@example.com",
                "password": "SecurePass123!"
            }
        }
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 422
        assert "username" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email."""
        payload = {
            "user": {
                "username": "differentuser",
                "email": "test@example.com",  # Already exists
                "password": "SecurePass123!"
            }
        }
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 422
        assert "email" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email format."""
        payload = {
            "user": {
                "username": "newuser",
                "email": "invalid-email",
                "password": "SecurePass123!"
            }
        }
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """Test registration with weak password."""
        payload = {
            "user": {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "weak"  # Too short, no uppercase, no special char
            }
        }
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username(self, client: AsyncClient):
        """Test registration with invalid username characters."""
        payload = {
            "user": {
                "username": "user@name",  # Invalid character
                "email": "newuser@example.com",
                "password": "SecurePass123!"
            }
        }
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields."""
        payload = {"user": {"username": "newuser"}}
        
        response = await client.post("/api/users", json=payload)
        
        assert response.status_code == 422


class TestUserLogin:
    """Tests for POST /api/users/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        payload = {
            "user": {
                "email": "test@example.com",
                "password": "TestPass123!"
            }
        }
        
        response = await client.post("/api/users/login", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["username"] == "testuser"
        assert "token" in data["user"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with incorrect password."""
        payload = {
            "user": {
                "email": "test@example.com",
                "password": "WrongPassword123!"
            }
        }
        
        response = await client.post("/api/users/login", json=payload)
        
        assert response.status_code == 401
        assert "credentials" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user."""
        payload = {
            "user": {
                "email": "nonexistent@example.com",
                "password": "TestPass123!"
            }
        }
        
        response = await client.post("/api/users/login", json=payload)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient):
        """Test login with missing fields."""
        payload = {"user": {"email": "test@example.com"}}
        
        response = await client.post("/api/users/login", json=payload)
        
        assert response.status_code == 422


class TestGetCurrentUser:
    """Tests for GET /api/user."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test getting current user information."""
        response = await client.get("/api/user", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert "token" in data["user"]

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without authentication."""
        response = await client.get("/api/user")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Token invalid_token"}
        response = await client.get("/api/user", headers=headers)
        
        assert response.status_code == 401


class TestUpdateUser:
    """Tests for PUT /api/user."""

    @pytest.mark.asyncio
    async def test_update_user_email(self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession):
        """Test updating user email."""
        payload = {
            "user": {
                "email": "newemail@example.com"
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "newemail@example.com"
        
        # Verify in database
        await db_session.refresh(test_user)
        assert test_user.email == "newemail@example.com"

    @pytest.mark.asyncio
    async def test_update_user_username(self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession):
        """Test updating username."""
        payload = {
            "user": {
                "username": "newusername"
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "newusername"
        
        # Verify in database
        await db_session.refresh(test_user)
        assert test_user.username == "newusername"

    @pytest.mark.asyncio
    async def test_update_user_password(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating password."""
        payload = {
            "user": {
                "password": "NewSecurePass123!"
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        
        # Try to login with new password
        login_payload = {
            "user": {
                "email": "test@example.com",
                "password": "NewSecurePass123!"
            }
        }
        login_response = await client.post("/api/users/login", json=login_payload)
        assert login_response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_user_bio(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating bio."""
        payload = {
            "user": {
                "bio": "Updated bio text"
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["bio"] == "Updated bio text"

    @pytest.mark.asyncio
    async def test_update_user_image(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating profile image."""
        payload = {
            "user": {
                "image": "https://example.com/newimage.jpg"
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["image"] == "https://example.com/newimage.jpg"

    @pytest.mark.asyncio
    async def test_update_user_duplicate_email(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test updating to an email that already exists."""
        payload = {
            "user": {
                "email": "test2@example.com"  # Belongs to test_user2
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_user_duplicate_username(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test updating to a username that already exists."""
        payload = {
            "user": {
                "username": "testuser2"  # Belongs to test_user2
            }
        }
        
        response = await client.put("/api/user", json=payload, headers=auth_headers)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_user_unauthorized(self, client: AsyncClient):
        """Test updating user without authentication."""
        payload = {"user": {"email": "newemail@example.com"}}
        
        response = await client.put("/api/user", json=payload)
        
        assert response.status_code == 401
