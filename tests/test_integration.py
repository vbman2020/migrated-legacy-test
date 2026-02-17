"""Integration tests for complete workflows."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class TestUserWorkflow:
    """Integration tests for complete user workflows."""

    @pytest.mark.asyncio
    async def test_user_registration_and_login_flow(self, client: AsyncClient):
        """Test complete user registration and login flow."""
        # Register user
        register_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "workflow@example.com",
                    "username": "workflowuser",
                    "password": "Password123!@#"
                }
            }
        )
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert "token" in register_data["user"]
        
        # Login with same credentials
        login_response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "workflow@example.com",
                    "password": "Password123!@#"
                }
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "token" in login_data["user"]
        
        # Get current user
        headers = {"Authorization": f"Token {login_data['user']['token']}"}
        user_response = await client.get("/api/user", headers=headers)
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert user_data["user"]["email"] == "workflow@example.com"

    @pytest.mark.asyncio
    async def test_user_profile_update_flow(self, client: AsyncClient, auth_headers: dict):
        """Test updating user profile."""
        # Update user
        update_response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={
                "user": {
                    "bio": "I am a test user",
                    "image": "https://example.com/avatar.jpg"
                }
            }
        )
        assert update_response.status_code == 200
        
        # Verify update
        user_response = await client.get("/api/user", headers=auth_headers)
        user_data = user_response.json()
        assert user_data["user"]["bio"] == "I am a test user"
        assert user_data["user"]["image"] == "https://example.com/avatar.jpg"


class TestArticleWorkflow:
    """Integration tests for complete article workflows."""

    @pytest.mark.asyncio
    async def test_article_crud_workflow(self, client: AsyncClient, auth_headers: dict):
        """Test complete article CRUD workflow."""
        # Create article
        create_response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Test Workflow Article",
                    "description": "Testing full workflow",
                    "body": "This is a test article for workflow testing",
                    "tagList": ["test", "workflow"]
                }
            }
        )
        assert create_response.status_code == 201
        created_data = create_response.json()
        slug = created_data["article"]["slug"]
        
        # Read article
        read_response = await client.get(f"/api/articles/{slug}")
        assert read_response.status_code == 200
        read_data = read_response.json()
        assert read_data["article"]["title"] == "Test Workflow Article"
        
        # Update article
        update_response = await client.put(
            f"/api/articles/{slug}",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated Workflow Article"
                }
            }
        )
        assert update_response.status_code == 200
        update_data = update_response.json()
        assert update_data["article"]["title"] == "Updated Workflow Article"
        
        # Delete article
        delete_response = await client.delete(
            f"/api/articles/{slug}",
            headers=auth_headers
        )
        assert delete_response.status_code == 204
        
        # Verify deletion
        get_response = await client.get(f"/api/articles/{slug}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_article_favorite_workflow(self, client: AsyncClient, test_article, auth_headers: dict):
        """Test article favorite/unfavorite workflow."""
        # Favorite article
        favorite_response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        assert favorite_response.status_code == 200
        favorite_data = favorite_response.json()
        assert favorite_data["article"]["favorited"] is True
        assert favorite_data["article"]["favoritesCount"] == 1
        
        # Verify in article list
        list_response = await client.get("/api/articles", headers=auth_headers)
        list_data = list_response.json()
        article = next(a for a in list_data["articles"] if a["slug"] == test_article.slug)
        assert article["favorited"] is True
        
        # Unfavorite article
        unfavorite_response = await client.delete(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        assert unfavorite_response.status_code == 200
        unfavorite_data = unfavorite_response.json()
        assert unfavorite_data["article"]["favorited"] is False
        assert unfavorite_data["article"]["favoritesCount"] == 0


class TestCommentWorkflow:
    """Integration tests for complete comment workflows."""

    @pytest.mark.asyncio
    async def test_comment_create_and_delete_workflow(self, client: AsyncClient, test_article, auth_headers: dict):
        """Test creating and deleting comments."""
        # Create comment
        create_response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={
                "comment": {
                    "body": "This is a test comment for workflow"
                }
            }
        )
        assert create_response.status_code == 201
        comment_data = create_response.json()
        comment_id = comment_data["comment"]["id"]
        
        # Get comments
        get_response = await client.get(f"/api/articles/{test_article.slug}/comments")
        get_data = get_response.json()
        assert len(get_data["comments"]) == 1
        assert get_data["comments"][0]["body"] == "This is a test comment for workflow"
        
        # Delete comment
        delete_response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{comment_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 204
        
        # Verify deletion
        verify_response = await client.get(f"/api/articles/{test_article.slug}/comments")
        verify_data = verify_response.json()
        assert len(verify_data["comments"]) == 0


class TestFollowWorkflow:
    """Integration tests for follow/unfollow workflows."""

    @pytest.mark.asyncio
    async def test_follow_and_feed_workflow(self, client: AsyncClient, test_user, test_user2, auth_headers: dict, auth_headers2: dict):
        """Test following user and seeing their articles in feed."""
        # Follow user2
        follow_response = await client.post(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        assert follow_response.status_code == 200
        
        # User2 creates an article
        article_response = await client.post(
            "/api/articles",
            headers=auth_headers2,
            json={
                "article": {
                    "title": "Article by followed user",
                    "description": "Description",
                    "body": "Body",
                    "tagList": []
                }
            }
        )
        assert article_response.status_code == 201
        
        # Check feed shows user2's article
        feed_response = await client.get("/api/articles/feed", headers=auth_headers)
        feed_data = feed_response.json()
        assert len(feed_data["articles"]) >= 1
        assert any(a["author"]["username"] == test_user2.username for a in feed_data["articles"])
        
        # Unfollow user2
        unfollow_response = await client.delete(
            f"/api/profiles/{test_user2.username}/follow",
            headers=auth_headers
        )
        assert unfollow_response.status_code == 200
        
        # Check feed is empty
        empty_feed_response = await client.get("/api/articles/feed", headers=auth_headers)
        empty_feed_data = empty_feed_response.json()
        assert len(empty_feed_data["articles"]) == 0


class TestComplexWorkflow:
    """Integration tests for complex multi-user scenarios."""

    @pytest.mark.asyncio
    async def test_multi_user_article_interaction(self, client: AsyncClient, test_user, test_user2, auth_headers: dict, auth_headers2: dict):
        """Test complex interaction between multiple users on articles."""
        # User1 creates article
        article_response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Collaborative Article",
                    "description": "Testing collaboration",
                    "body": "This article will have multiple interactions",
                    "tagList": ["collaboration"]
                }
            }
        )
        slug = article_response.json()["article"]["slug"]
        
        # User2 favorites the article
        await client.post(f"/api/articles/{slug}/favorite", headers=auth_headers2)
        
        # User2 comments on the article
        comment_response = await client.post(
            f"/api/articles/{slug}/comments",
            headers=auth_headers2,
            json={"comment": {"body": "Great article!"}}
        )
        comment_id = comment_response.json()["comment"]["id"]
        
        # User1 checks article and sees favorite count
        article_check = await client.get(f"/api/articles/{slug}", headers=auth_headers)
        article_data = article_check.json()
        assert article_data["article"]["favoritesCount"] == 1
        assert article_data["article"]["favorited"] is False  # User1 hasn't favorited
        
        # User1 checks comments
        comments_response = await client.get(f"/api/articles/{slug}/comments", headers=auth_headers)
        comments_data = comments_response.json()
        assert len(comments_data["comments"]) == 1
        assert comments_data["comments"][0]["author"]["username"] == test_user2.username
        
        # User2 deletes their comment
        await client.delete(
            f"/api/articles/{slug}/comments/{comment_id}",
            headers=auth_headers2
        )
        
        # Verify comment is deleted
        verify_comments = await client.get(f"/api/articles/{slug}/comments")
        assert len(verify_comments.json()["comments"]) == 0
