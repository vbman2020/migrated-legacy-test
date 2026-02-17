"""Integration tests for complete workflows."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestCompleteUserJourney:
    """Test complete user journeys through the application."""

    @pytest.mark.asyncio
    async def test_user_registration_to_article_creation(self, client: AsyncClient):
        """Test complete flow: register, login, create article, get article."""
        # 1. Register a new user
        register_payload = {
            "user": {
                "username": "journeyuser",
                "email": "journey@example.com",
                "password": "SecurePass123!"
            }
        }
        register_response = await client.post("/api/users", json=register_payload)
        assert register_response.status_code == 201
        token = register_response.json()["user"]["token"]
        headers = {"Authorization": f"Token {token}"}
        
        # 2. Create an article
        article_payload = {
            "article": {
                "title": "My First Article",
                "description": "This is my first article",
                "body": "Article body content here",
                "tagList": ["first", "article"]
            }
        }
        create_response = await client.post("/api/articles", json=article_payload, headers=headers)
        assert create_response.status_code == 201
        slug = create_response.json()["article"]["slug"]
        
        # 3. Get the article
        get_response = await client.get(f"/api/articles/{slug}")
        assert get_response.status_code == 200
        assert get_response.json()["article"]["title"] == "My First Article"

    @pytest.mark.asyncio
    async def test_follow_and_feed_workflow(self, client: AsyncClient, test_user: User, test_user2: User, test_article: Article, auth_headers: dict):
        """Test following a user and seeing their articles in feed."""
        # 1. Follow test_user (who has an article)
        follow_response = await client.post(
            f"/api/profiles/{test_user.username}/follow",
            headers=auth_headers
        )
        assert follow_response.status_code == 200
        assert follow_response.json()["profile"]["following"] is True
        
        # 2. Get feed - should include test_user's article
        feed_response = await client.get("/api/articles/feed", headers=auth_headers)
        assert feed_response.status_code == 200
        articles = feed_response.json()["articles"]
        article_slugs = [a["slug"] for a in articles]
        assert test_article.slug in article_slugs

    @pytest.mark.asyncio
    async def test_article_with_comments_workflow(self, client: AsyncClient, test_article: Article, auth_headers: dict, auth_headers2: dict):
        """Test creating article and adding comments."""
        # 1. Add comment as user2
        comment_payload = {
            "comment": {
                "body": "Great article!"
            }
        }
        comment_response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            json=comment_payload,
            headers=auth_headers2
        )
        assert comment_response.status_code == 201
        comment_id = comment_response.json()["comment"]["id"]
        
        # 2. Get comments
        get_comments_response = await client.get(f"/api/articles/{test_article.slug}/comments")
        assert get_comments_response.status_code == 200
        comments = get_comments_response.json()["comments"]
        assert len(comments) >= 1
        assert any(c["id"] == comment_id for c in comments)
        
        # 3. Delete comment as author
        delete_response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{comment_id}",
            headers=auth_headers2
        )
        assert delete_response.status_code == 204

    @pytest.mark.asyncio
    async def test_favorite_and_filter_workflow(self, client: AsyncClient, test_article: Article, auth_headers: dict, test_user: User):
        """Test favoriting articles and filtering by favorited."""
        # 1. Favorite an article
        favorite_response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        assert favorite_response.status_code == 201
        assert favorite_response.json()["article"]["favorited"] is True
        
        # 2. Filter articles by favorited
        filter_response = await client.get(
            f"/api/articles?favorited={test_user.username}",
            headers=auth_headers
        )
        assert filter_response.status_code == 200
        articles = filter_response.json()["articles"]
        assert len(articles) >= 1
        assert all(a["favorited"] is True for a in articles)

    @pytest.mark.asyncio
    async def test_update_profile_workflow(self, client: AsyncClient, auth_headers: dict):
        """Test updating user profile information."""
        # 1. Get current user
        get_response = await client.get("/api/user", headers=auth_headers)
        assert get_response.status_code == 200
        original_bio = get_response.json()["user"].get("bio", "")
        
        # 2. Update bio and image
        update_payload = {
            "user": {
                "bio": "Updated bio information",
                "image": "https://example.com/newavatar.jpg"
            }
        }
        update_response = await client.put("/api/user", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200
        assert update_response.json()["user"]["bio"] == "Updated bio information"
        assert update_response.json()["user"]["image"] == "https://example.com/newavatar.jpg"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_pagination_edge_cases(self, client: AsyncClient):
        """Test pagination with edge case values."""
        # Test with limit at maximum
        response = await client.get("/api/articles?limit=100")
        assert response.status_code == 200
        
        # Test with limit above maximum
        response = await client.get("/api/articles?limit=101")
        assert response.status_code == 422
        
        # Test with negative offset
        response = await client.get("/api/articles?offset=-1")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_special_characters_in_article(self, client: AsyncClient, auth_headers: dict):
        """Test article creation with special characters."""
        payload = {
            "article": {
                "title": "Test Article with émojis 🚀 and spëcial çhars",
                "description": "Testing special characters: @#$%^&*()",
                "body": "Body with <html>tags</html> and 'quotes'",
                "tagList": ["special-chars", "émoji"]
            }
        }
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert "slug" in data["article"]

    @pytest.mark.asyncio
    async def test_concurrent_slug_generation(self, client: AsyncClient, auth_headers: dict, auth_headers2: dict):
        """Test that concurrent articles with same title get unique slugs."""
        payload = {
            "article": {
                "title": "Same Title",
                "description": "Description",
                "body": "Body content"
            }
        }
        
        # Create two articles with same title
        response1 = await client.post("/api/articles", json=payload, headers=auth_headers)
        response2 = await client.post("/api/articles", json=payload, headers=auth_headers2)
        
        assert response1.status_code == 201
        assert response2.status_code == 201
        
        slug1 = response1.json()["article"]["slug"]
        slug2 = response2.json()["article"]["slug"]
        
        # Slugs should be different
        assert slug1 != slug2

    @pytest.mark.asyncio
    async def test_very_long_article_body(self, client: AsyncClient, auth_headers: dict):
        """Test article with very long body (near limit)."""
        long_body = "a" * 99999  # Just under limit
        
        payload = {
            "article": {
                "title": "Long Article",
                "description": "Testing long body",
                "body": long_body
            }
        }
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_article_body_exceeds_limit(self, client: AsyncClient, auth_headers: dict):
        """Test article with body exceeding maximum length."""
        too_long_body = "a" * 100001  # Exceeds limit
        
        payload = {
            "article": {
                "title": "Too Long Article",
                "description": "Testing body limit",
                "body": too_long_body
            }
        }
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        assert response.status_code == 422
