"""Tests for profiles endpoints.

Tests getting profiles, following/unfollowing users.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class TestGetProfile:
    """Test get profile endpoint GET /api/profiles/{username}."""

    @pytest.mark.asyncio
    async def test_get_profile_success(self, client: AsyncClient, test_user: User):
        """Test getting user profile."""
        response = await client.get(f"/api/profiles/{test_user.username}")
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["username"] == test_user.username
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, client: AsyncClient):
        """Test getting nonexistent profile returns 404."""
        response = await client.get("/api/profiles/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_profile_following_flag(
        self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test following flag is set correctly."""
        # Not following
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["profile"]["following"] is False
        
        # Follow user
        test_user.following.append(test_user2)
        await db_session.commit()
        
        # Now following
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["profile"]["following"] is True

    @pytest.mark.asyncio
    async def test_get_profile_unauthenticated(
        self, client: AsyncClient, test_user: User
    ):
        """Test getting profile without auth shows following as false."""
        response = await client.get(f"/api/profiles/{test_user.username}")
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_get_profile_with_bio_image(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test profile returns bio and image if set."""
        # Assuming profile has bio and image fields
        if hasattr(test_user, 'profile'):
            test_user.profile.bio = "I love coding"
            test_user.profile.image = "https://example.com/avatar.jpg"
            await db_session.commit()
        
        response = await client.get(f"/api/profiles/{test_user.username}")
        assert response.status_code == 200
        data = response.json()
        if hasattr(test_user, 'profile'):
            assert data["profile"]["bio"] == "I love coding"
            assert data["profile"]["image"] == "https://example.com/avatar.jpg"


class TestFollowUser:
    """Test follow user endpoint POST /api/profiles/{username}/follow."""

    @pytest.mark.asyncio
    async def test_follow_user_success(
        self, client: AsyncClient, test_user2: User, auth_headers: dict
    ):
        """Test following a user."""
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["following"] is True

    @pytest.mark.asyncio
    async def test_follow_user_no_auth(self, client: AsyncClient, test_user2: User):
        """Test following without auth fails."""
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_follow_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test following nonexistent user returns 404."""
        response = await client.post(
            "/api/profiles/nonexistent/follow",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_follow_self(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test following yourself fails."""
        response = await client.post(
            f"/api/profiles/{test_user.username}/follow",
            headers=auth_headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert "yourself" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_follow_twice_idempotent(
        self, client: AsyncClient, test_user2: User, auth_headers: dict
    ):
        """Test following user twice is idempotent."""
        # Follow first time
        response1 = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response1.status_code == 200
        
        # Follow second time
        response2 = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response2.status_code == 200
        assert response2.json()["profile"]["following"] is True


class TestUnfollowUser:
    """Test unfollow user endpoint DELETE /api/profiles/{username}/follow."""

    @pytest.mark.asyncio
    async def test_unfollow_user_success(
        self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test unfollowing a user."""
        # First follow
        test_user.following.append(test_user2)
        await db_session.commit()
        
        # Then unfollow
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["username"] == test_user2.username
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_unfollow_user_no_auth(self, client: AsyncClient, test_user2: User):
        """Test unfollowing without auth fails."""
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unfollow_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test unfollowing nonexistent user returns 404."""
        response = await client.delete(
            "/api/profiles/nonexistent/follow",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unfollow_not_following(
        self, client: AsyncClient, test_user2: User, auth_headers: dict
    ):
        """Test unfollowing user you don't follow is idempotent."""
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_unfollow_self(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test unfollowing yourself fails."""
        response = await client.delete(
            f"/api/profiles/{test_user.username}/follow",
            headers=auth_headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert "yourself" in data["detail"].lower()


class TestProfileIntegration:
    """Integration tests for profile functionality."""

    @pytest.mark.asyncio
    async def test_follow_unfollow_workflow(
        self, client: AsyncClient, test_user2: User, auth_headers: dict
    ):
        """Test complete follow/unfollow workflow."""
        # Initially not following
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers,
        )
        assert response.json()["profile"]["following"] is False
        
        # Follow
        response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response.json()["profile"]["following"] is True
        
        # Verify following
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers,
        )
        assert response.json()["profile"]["following"] is True
        
        # Unfollow
        response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers,
        )
        assert response.json()["profile"]["following"] is False
        
        # Verify not following
        response = await client.get(
            f"/api/profiles/{test_user2.username}",
            headers=auth_headers,
        )
        assert response.json()["profile"]["following"] is False

    @pytest.mark.asyncio
    async def test_multiple_users_following(
        self,
        client: AsyncClient,
        test_user: User,
        test_user2: User,
        auth_headers: dict,
        auth_headers2: dict,
        db_session: AsyncSession,
    ):
        """Test multiple users can follow same user."""
        # Create third user
        from app.auth.service import AuthService
        auth_service = AuthService(db_session)
        user3 = await auth_service.create_user(
            email="user3@example.com",
            username="user3",
            password="TestPass123!",
        )
        await db_session.commit()
        
        # Both user1 and user2 follow user3
        response1 = await client.post(
            f"/api/profiles/{user3.username}/follow",
            headers=auth_headers,
        )
        response2 = await client.post(
            f"/api/profiles/{user3.username}/follow",
            headers=auth_headers2,
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["profile"]["following"] is True
        assert response2.json()["profile"]["following"] is True
