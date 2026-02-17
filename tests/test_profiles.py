"""Tests for profile endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class TestGetProfile:
    """Tests for GET /api/profiles/{username} endpoint."""

    @pytest.mark.asyncio
    async def test_get_profile_authenticated(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test getting profile while authenticated."""
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["bio"] == test_user2.bio
        assert data["profile"]["image"] == test_user2.image
        assert "following" in data["profile"]
        assert isinstance(data["profile"]["following"], bool)

    @pytest.mark.asyncio
    async def test_get_profile_unauthenticated(self, client: AsyncClient, test_user: User):
        """Test getting profile without authentication."""
        response = await client.get(f"/api/profiles/{test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user.username
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, client: AsyncClient):
        """Test getting non-existent profile."""
        response = await client.get("/api/profiles/nonexistentuser")
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_own_profile(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test getting own profile."""
        response = await client.get(
            f"/api/profiles/{test_user.username}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["username"] == test_user.username
        # Should not be following yourself
        assert data["profile"]["following"] is False


class TestFollowUser:
    """Tests for POST /api/profiles/{username}/follow endpoint."""

    @pytest.mark.asyncio
    async def test_follow_user_success(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test successfully following a user."""
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["following"] is True

    @pytest.mark.asyncio
    async def test_follow_user_already_following(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test following a user that's already followed (idempotent)."""
        # Follow first time
        await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        # Follow again
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is True

    @pytest.mark.asyncio
    async def test_follow_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test following non-existent user."""
        response = await client.post(
            "/api/profiles/nonexistentuser/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_follow_user_no_auth(self, client: AsyncClient, test_user2: User):
        """Test following without authentication."""
        response = await client.post(f"/api/profiles/{test_user2.username}/follow")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_follow_self(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test following yourself (should be prevented)."""
        response = await client.post(
            f"/api/profiles/{test_user.username}/follow",
            headers=auth_headers
        )
        
        # Should either return 422 or 200 with following=False
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_follow_reflects_in_profile(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test that follow status is reflected when getting profile."""
        # Follow user
        await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        # Get profile
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is True


class TestUnfollowUser:
    """Tests for DELETE /api/profiles/{username}/follow endpoint."""

    @pytest.mark.asyncio
    async def test_unfollow_user_success(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test successfully unfollowing a user."""
        # First follow
        await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        # Then unfollow
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_unfollow_user_not_following(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test unfollowing a user that's not followed (idempotent)."""
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_unfollow_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test unfollowing non-existent user."""
        response = await client.delete(
            "/api/profiles/nonexistentuser/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unfollow_user_no_auth(self, client: AsyncClient, test_user2: User):
        """Test unfollowing without authentication."""
        response = await client.delete(f"/api/profiles/{test_user2.username}/follow")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unfollow_reflects_in_profile(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test that unfollow status is reflected when getting profile."""
        # Follow then unfollow
        await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        # Get profile
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_follow_unfollow_cycle(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test multiple follow/unfollow cycles."""
        # Follow
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        assert response.json()["profile"]["following"] is True
        
        # Unfollow
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        assert response.json()["profile"]["following"] is False
        
        # Follow again
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        assert response.json()["profile"]["following"] is True
