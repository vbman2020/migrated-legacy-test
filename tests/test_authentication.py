"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import AuthService


class TestUserRegistration:
    """Tests for POST /api/users (user registration)."""
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful user registration."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "password123"
                }
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "newuser@example.com"
        assert "token" in data["user"]
        assert "password" not in data["user"]
    
    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "differentuser",
                    "email": "test@example.com",  # Same as test_user
                    "password": "password123"
                }
            }
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "email" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate username fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "testuser",  # Same as test_user
                    "email": "different@example.com",
                    "password": "password123"
                }
            }
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "username" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_user_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "newuser",
                    "email": "notanemail",
                    "password": "password123"
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_user_short_password(self, client: AsyncClient):
        """Test registration with short password fails."""
        response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "short"
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_user_missing_user_key(self, client: AsyncClient):
        """Test registration without 'user' wrapper key fails."""
        response = await client.post(
            "/api/users",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 422


class TestUserLogin:
    """Tests for POST /api/users/login."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "password123"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert "token" in data["user"]
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password fails."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "wrongpassword"
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email fails."""
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "nonexistent@example.com",
                    "password": "password123"
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_missing_user_key(self, client: AsyncClient, test_user: User):
        """Test login without 'user' wrapper key fails."""
        response = await client.post(
            "/api/users/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 422


class TestGetCurrentUser:
    """Tests for GET /api/user."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test getting current user with valid token."""
        response = await client.get("/api/user", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert "token" in data["user"]
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_auth(self, client: AsyncClient):
        """Test getting current user without authentication fails."""
        response = await client.get("/api/user")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token fails."""
        response = await client.get(
            "/api/user",
            headers={"Authorization": "Token invalidtoken"}
        )
        
        assert response.status_code == 401


class TestUpdateCurrentUser:
    """Tests for PUT /api/user."""
    
    @pytest.mark.asyncio
    async def test_update_user_username(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating username."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "username": "updateduser"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "updateduser"
    
    @pytest.mark.asyncio
    async def test_update_user_email(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating email."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "email": "updated@example.com"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "updated@example.com"
    
    @pytest.mark.asyncio
    async def test_update_user_password(self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession):
        """Test updating password."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "password": "newpassword123"
                }
            }
        )
        
        assert response.status_code == 200
        
        # Verify can login with new password
        login_response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "newpassword123"
                }
            }
        )
        assert login_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_update_user_bio_and_image(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test updating bio and image."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "bio": "Updated bio",
                    "image": "https://example.com/image.jpg"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["bio"] == "Updated bio"
        assert data["user"]["image"] == "https://example.com/image.jpg"
    
    @pytest.mark.asyncio
    async def test_update_user_duplicate_username(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test updating to duplicate username fails."""
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "username": "testuser2"  # test_user2's username
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_update_user_no_auth(self, client: AsyncClient):
        """Test updating user without authentication fails."""
        response = await client.put(
            "/api/user",
            json={
                "user": {
                    "username": "updateduser"
                }
            }
        )
        
        assert response.status_code == 401
