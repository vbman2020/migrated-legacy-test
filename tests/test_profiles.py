"""Tests for profile endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class TestGetProfile:
    """Tests for GET /api/profiles/{username}."""

    @pytest.mark.asyncio
    async def test_get_profile_success(self, client: AsyncClient, test_user: User):
        """Test getting a user profile."""
        response = await client.get(f"/api/profiles/{test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user.username
        assert data["profile"]["bio"] == "Test bio"
        assert "image" in data["profile"]
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_get_profile_authenticated(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test getting profile as authenticated user."""
        response = await client.get(f"/api/profiles/{test_user.username}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert "following" in data["profile"]

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, client: AsyncClient):
        """Test getting non-existent profile."""
        response = await client.get("/api/profiles/nonexistentuser")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_profile_following_status(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test profile shows correct following status."""
        # First follow the user
        await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        # Then get their profile
        response = await client.get(f"/api/profiles/{test_user2.username}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is True


class TestFollowUser:
    """Tests for POST /api/profiles/{username}/follow."""

    @pytest.mark.asyncio
    async def test_follow_user_success(self, client: AsyncClient, test_user2: User, auth_headers: dict):
        """Test following a user."""
        response = await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["following"] is True

    @pytest.mark.asyncio
    async def test_follow_user_twice(self, client: AsyncClient, test_user2: User, auth_headers: dict):
        """Test following a user twice (idempotent)."""
        # First follow
        await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        # Second follow
        response = await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is True

    @pytest.mark.asyncio
    async def test_follow_user_unauthorized(self, client: AsyncClient, test_user2: User):
        """Test following user without authentication."""
        response = await client.post(f"/api/profiles/{test_user2.username}/follow")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_follow_self(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test following yourself."""
        response = await client.post(f"/api/profiles/{test_user.username}/follow", headers=auth_headers)
        
        # Should fail or be handled gracefully
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_follow_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test following non-existent user."""
        response = await client.post("/api/profiles/nonexistentuser/follow", headers=auth_headers)
        
        assert response.status_code == 404


class TestUnfollowUser:
    """Tests for DELETE /api/profiles/{username}/follow."""

    @pytest.mark.asyncio
    async def test_unfollow_user_success(self, client: AsyncClient, test_user2: User, auth_headers: dict):
        """Test unfollowing a user."""
        # First follow
        await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        # Then unfollow
        response = await client.delete(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_unfollow_user_not_following(self, client: AsyncClient, test_user2: User, auth_headers: dict):
        """Test unfollowing a user you're not following."""
        response = await client.delete(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_unfollow_user_unauthorized(self, client: AsyncClient, test_user2: User):
        """Test unfollowing user without authentication."""
        response = await client.delete(f"/api/profiles/{test_user2.username}/follow")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unfollow_self(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test unfollowing yourself."""
        response = await client.delete(f"/api/profiles/{test_user.username}/follow", headers=auth_headers)
        
        # Should fail or be handled gracefully
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_unfollow_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test unfollowing non-existent user."""
        response = await client.delete("/api/profiles/nonexistentuser/follow", headers=auth_headers)
        
        assert response.status_code == 404
