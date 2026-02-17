"""Integration tests for complete user workflows."""
import pytest
from httpx import AsyncClient


class TestCompleteUserJourney:
    """Test complete user journey from registration to article management."""
    
    @pytest.mark.asyncio
    async def test_register_login_create_article_workflow(self, client: AsyncClient):
        """Test user registration, login, and creating an article."""
        # Register user
        register_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "journeyuser",
                    "email": "journey@example.com",
                    "password": "password123"
                }
            }
        )
        assert register_response.status_code == 201
        token = register_response.json()["user"]["token"]
        
        # Create article
        article_response = await client.post(
            "/api/articles",
            headers={"Authorization": f"Token {token}"},
            json={
                "article": {
                    "title": "My First Article",
                    "description": "This is my first article",
                    "body": "Article content goes here",
                    "tagList": ["introduction"]
                }
            }
        )
        assert article_response.status_code == 201
        slug = article_response.json()["article"]["slug"]
        
        # Get article
        get_response = await client.get(f"/api/articles/{slug}")
        assert get_response.status_code == 200
        assert get_response.json()["article"]["author"]["username"] == "journeyuser"
    
    @pytest.mark.asyncio
    async def test_follow_and_feed_workflow(self, client: AsyncClient, test_user, test_article):
        """Test following a user and seeing their articles in feed."""
        # Register second user
        register_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "followeruser",
                    "email": "follower@example.com",
                    "password": "password123"
                }
            }
        )
        assert register_response.status_code == 201
        token = register_response.json()["user"]["token"]
        headers = {"Authorization": f"Token {token}"}
        
        # Follow first user
        follow_response = await client.post(
            f"/api/profiles/{test_user.username}/follow",
            headers=headers
        )
        assert follow_response.status_code == 200
        assert follow_response.json()["profile"]["following"] is True
        
        # Check feed contains followed user's articles
        feed_response = await client.get("/api/articles/feed", headers=headers)
        assert feed_response.status_code == 200
        articles = feed_response.json()["articles"]
        assert len(articles) > 0
        assert articles[0]["author"]["username"] == test_user.username
    
    @pytest.mark.asyncio
    async def test_favorite_article_workflow(self, client: AsyncClient, test_article):
        """Test favoriting an article affects counts and filters."""
        # Register user
        register_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "favoriteuser",
                    "email": "favorite@example.com",
                    "password": "password123"
                }
            }
        )
        token = register_response.json()["user"]["token"]
        headers = {"Authorization": f"Token {token}"}
        
        # Favorite article
        favorite_response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=headers
        )
        assert favorite_response.status_code == 201
        assert favorite_response.json()["article"]["favorited"] is True
        assert favorite_response.json()["article"]["favoritesCount"] >= 1
        
        # Check article appears in favorited filter
        filter_response = await client.get(
            "/api/articles?favorited=favoriteuser",
            headers=headers
        )
        assert filter_response.status_code == 200
        articles = filter_response.json()["articles"]
        assert len(articles) > 0
        assert articles[0]["slug"] == test_article.slug


class TestArticleCommentWorkflow:
    """Test article and comment interactions."""
    
    @pytest.mark.asyncio
    async def test_create_article_add_comments_workflow(self, client: AsyncClient):
        """Test creating article and adding comments."""
        # Register two users
        user1_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "author",
                    "email": "author@example.com",
                    "password": "password123"
                }
            }
        )
        token1 = user1_response.json()["user"]["token"]
        
        user2_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "username": "commenter",
                    "email": "commenter@example.com",
                    "password": "password123"
                }
            }
        )
        token2 = user2_response.json()["user"]["token"]
        
        # User1 creates article
        article_response = await client.post(
            "/api/articles",
            headers={"Authorization": f"Token {token1}"},
            json={
                "article": {
                    "title": "Discussion Article",
                    "description": "Let's discuss",
                    "body": "What do you think?"
                }
            }
        )
        slug = article_response.json()["article"]["slug"]
        
        # User2 adds comment
        comment_response = await client.post(
            f"/api/articles/{slug}/comments",
            headers={"Authorization": f"Token {token2}"},
            json={
                "comment": {
                    "body": "Great article!"
                }
            }
        )
        assert comment_response.status_code == 201
        comment_id = comment_response.json()["comment"]["id"]
        
        # Get comments
        comments_response = await client.get(f"/api/articles/{slug}/comments")
        assert len(comments_response.json()["comments"]) == 1
        assert comments_response.json()["comments"][0]["author"]["username"] == "commenter"
        
        # User2 deletes their comment
        delete_response = await client.delete(
            f"/api/articles/{slug}/comments/{comment_id}",
            headers={"Authorization": f"Token {token2}"}
        )
        assert delete_response.status_code == 204
        
        # Verify comment is gone
        final_comments = await client.get(f"/api/articles/{slug}/comments")
        assert len(final_comments.json()["comments"]) == 0
