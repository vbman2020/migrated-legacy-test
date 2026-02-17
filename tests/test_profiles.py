"""Tests for profile endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class TestGetProfile:
    """Tests for GET /api/profiles/{username}."""
    
    @pytest.mark.asyncio
    async def test_get_profile_unauthenticated(self, client: AsyncClient, test_user: User):
        """Test getting profile without authentication."""
        response = await client.get(f"/api/profiles/{test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == "testuser"
        assert data["profile"]["following"] is False
    
    @pytest.mark.asyncio
    async def test_get_profile_authenticated(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers2: dict):
        """Test getting profile while authenticated."""
        response = await client.get(f"/api/profiles/{test_user.username}", headers=auth_headers2)
        
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == "testuser"
        assert data["profile"]["following"] is False
    
    @pytest.mark.asyncio
    async def test_get_profile_nonexistent(self, client: AsyncClient):
        """Test getting non-existent profile returns 404."""
        response = await client.get("/api/profiles/nonexistent")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_profile_includes_bio_and_image(self, client: AsyncClient, test_user: User):
        """Test profile response includes bio and image."""
        response = await client.get(f"/api/profiles/{test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert "bio" in data["profile"]
        assert "image" in data["profile"]


class TestFollowUser:
    """Tests for POST /api/profiles/{username}/follow."""
    
    @pytest.mark.asyncio
    async def test_follow_user_success(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test successfully following a user."""
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["username"] == "testuser2"
        assert data["profile"]["following"] is True
    
    @pytest.mark.asyncio
    async def test_follow_user_already_following(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict):
        """Test following a user that's already followed (idempotent)."""
        # Follow once
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
    async def test_follow_self(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test following yourself fails."""
        response = await client.post(
            f"/api/profiles/{test_user.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_follow_nonexistent_user(self, client: AsyncClient, auth_headers: dict):
        """Test following non-existent user returns 404."""
        response = await client.post(
            "/api/profiles/nonexistent/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_follow_no_auth(self, client: AsyncClient, test_user2: User):
        """Test following without authentication fails."""
        response = await client.post(f"/api/profiles/{test_user2.username}/follow")
        
        assert response.status_code == 401


class TestUnfollowUser:
    """Tests for DELETE /api/profiles/{username}/follow."""
    
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
        assert data["profile"]["username"] == "testuser2"
        assert data["profile"]["following"] is False
    
    @pytest.mark.asyncio
    async def test_unfollow_user_not_following(self, client: AsyncClient, test_user2: User, auth_headers: dict):
        """Test unfollowing a user that's not followed (idempotent)."""
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is False
    
    @pytest.mark.asyncio
    async def test_unfollow_nonexistent_user(self, client: AsyncClient, auth_headers: dict):
        """Test unfollowing non-existent user returns 404."""
        response = await client.delete(
            "/api/profiles/nonexistent/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_unfollow_no_auth(self, client: AsyncClient, test_user2: User):
        """Test unfollowing without authentication fails."""
        response = await client.delete(f"/api/profiles/{test_user2.username}/follow")
        
        assert response.status_code == 401


class TestFollowingStatus:
    """Tests for following status in profile responses."""
    
    @pytest.mark.asyncio
    async def test_following_status_reflects_relationship(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict, auth_headers2: dict):
        """Test following status is correct from different user perspectives."""
        # User1 follows User2
        await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        
        # User1 checks User2's profile - should show following=True
        response1 = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers
        )
        assert response1.json()["profile"]["following"] is True
        
        # User2 checks User1's profile - should show following=False
        response2 = await client.get(
            f"/api/profiles/{test_user.username}",
            headers=auth_headers2
        )
        assert response2.json()["profile"]["following"] is False
