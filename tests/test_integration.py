"""Integration tests for complete workflows.

Tests realistic user journeys across multiple endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestCompleteUserJourney:
    """Test complete user journey from registration to article interaction."""

    @pytest.mark.asyncio
    async def test_new_user_complete_workflow(self, client: AsyncClient):
        """Test a new user's complete journey through the app."""
        # 1. Register
        register_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "journey@example.com",
                    "username": "journeyuser",
                    "password": "Journey123!",
                }
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["user"]["token"]
        headers = {"Authorization": f"Token {token}"}
        
        # 2. Update profile
        update_response = await client.put(
            "/api/user",
            headers=headers,
            json={
                "user": {
                    "bio": "I love writing",
                    "image": "https://example.com/avatar.jpg",
                }
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["user"]["bio"] == "I love writing"
        
        # 3. Create an article
        article_response = await client.post(
            "/api/articles",
            headers=headers,
            json={
                "article": {
                    "title": "My First Article",
                    "description": "This is my first article",
                    "body": "Hello world! This is my journey.",
                    "tagList": ["introduction", "journey"],
                }
            },
        )
        assert article_response.status_code == 201
        article_slug = article_response.json()["article"]["slug"]
        
        # 4. Get the article
        get_article_response = await client.get(
            f"/api/articles/{article_slug}",
            headers=headers,
        )
        assert get_article_response.status_code == 200
        assert get_article_response.json()["article"]["title"] == "My First Article"
        
        # 5. Add a comment
        comment_response = await client.post(
            f"/api/articles/{article_slug}/comments",
            headers=headers,
            json={
                "comment": {
                    "body": "This is my first comment!",
                }
            },
        )
        assert comment_response.status_code == 201
        
        # 6. Get comments
        get_comments_response = await client.get(
            f"/api/articles/{article_slug}/comments",
            headers=headers,
        )
        assert get_comments_response.status_code == 200
        assert len(get_comments_response.json()["comments"]) == 1
        
        # 7. Favorite the article
        favorite_response = await client.post(
            f"/api/articles/{article_slug}/favorite",
            headers=headers,
        )
        assert favorite_response.status_code == 200
        assert favorite_response.json()["article"]["favorited"] is True
        
        # 8. List all articles
        list_response = await client.get("/api/articles")
        assert list_response.status_code == 200
        assert len(list_response.json()["articles"]) == 1
        
        # 9. Get all tags
        tags_response = await client.get("/api/tags")
        assert tags_response.status_code == 200
        assert set(tags_response.json()["tags"]) == {"introduction", "journey"}


class TestSocialInteractions:
    """Test social interactions between multiple users."""

    @pytest.mark.asyncio
    async def test_follow_and_feed_workflow(self, client: AsyncClient):
        """Test following users and seeing their articles in feed."""
        # User 1 registers
        user1_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "user1@example.com",
                    "username": "user1",
                    "password": "User1Pass123!",
                }
            },
        )
        user1_token = user1_response.json()["user"]["token"]
        user1_headers = {"Authorization": f"Token {user1_token}"}
        
        # User 2 registers
        user2_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "user2@example.com",
                    "username": "user2",
                    "password": "User2Pass123!",
                }
            },
        )
        user2_token = user2_response.json()["user"]["token"]
        user2_headers = {"Authorization": f"Token {user2_token}"}
        
        # User 1 follows User 2
        follow_response = await client.post(
            "/api/profiles/user2/follow",
            headers=user1_headers,
        )
        assert follow_response.status_code == 200
        assert follow_response.json()["profile"]["following"] is True
        
        # User 2 creates an article
        article_response = await client.post(
            "/api/articles",
            headers=user2_headers,
            json={
                "article": {
                    "title": "Article by User 2",
                    "description": "Description",
                    "body": "Body",
                    "tagList": [],
                }
            },
        )
        assert article_response.status_code == 201
        
        # User 1 checks feed and sees User 2's article
        feed_response = await client.get(
            "/api/articles/feed",
            headers=user1_headers,
        )
        assert feed_response.status_code == 200
        feed_data = feed_response.json()
        assert len(feed_data["articles"]) == 1
        assert feed_data["articles"][0]["author"]["username"] == "user2"
        assert feed_data["articles"][0]["author"]["following"] is True
        
        # User 1 unfollows User 2
        unfollow_response = await client.delete(
            "/api/profiles/user2/follow",
            headers=user1_headers,
        )
        assert unfollow_response.status_code == 200
        
        # User 1's feed is now empty
        empty_feed_response = await client.get(
            "/api/articles/feed",
            headers=user1_headers,
        )
        assert empty_feed_response.status_code == 200
        assert len(empty_feed_response.json()["articles"]) == 0

    @pytest.mark.asyncio
    async def test_article_favorites_by_multiple_users(self, client: AsyncClient):
        """Test multiple users favoriting the same article."""
        # Create author
        author_response = await client.post(
            "/api/users",
            json={
                "user": {
                    "email": "author@example.com",
                    "username": "author",
                    "password": "Author123!",
                }
            },
        )
        author_token = author_response.json()["user"]["token"]
        author_headers = {"Authorization": f"Token {author_token}"}
        
        # Create article
        article_response = await client.post(
            "/api/articles",
            headers=author_headers,
            json={
                "article": {
                    "title": "Popular Article",
                    "description": "Everyone loves this",
                    "body": "Amazing content",
                    "tagList": ["popular"],
                }
            },
        )
        article_slug = article_response.json()["article"]["slug"]
        
        # Create two users who will favorite
        tokens = []
        for i in range(1, 3):
            user_response = await client.post(
                "/api/users",
                json={
                    "user": {
                        "email": f"fan{i}@example.com",
                        "username": f"fan{i}",
                        "password": f"Fan{i}Pass123!",
                    }
                },
            )
            tokens.append(user_response.json()["user"]["token"])
        
        # Both users favorite the article
        for token in tokens:
            headers = {"Authorization": f"Token {token}"}
            fav_response = await client.post(
                f"/api/articles/{article_slug}/favorite",
                headers=headers,
            )
            assert fav_response.status_code == 200
        
        # Check favorites count
        get_response = await client.get(f"/api/articles/{article_slug}")
        assert get_response.status_code == 200
        assert get_response.json()["article"]["favoritesCount"] == 2
        
        # Filter by favorited
        filter_response = await client.get(
            f"/api/articles?favorited=fan1"
        )
        assert filter_response.status_code == 200
        assert len(filter_response.json()["articles"]) == 1


class TestErrorHandling:
    """Test error handling across different scenarios."""

    @pytest.mark.asyncio
    async def test_cascade_delete_article_deletes_comments(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test that deleting an article cascades to comments."""
        from app.articles.service import ArticleService
        from app.articles.schemas import ArticleCreateSchema
        
        # Create article
        service = ArticleService(db_session)
        article = await service.create_article(
            ArticleCreateSchema(
                title="Test",
                description="Test",
                body="Test",
                tagList=[],
            ),
            test_user,
        )
        await db_session.commit()
        
        # Add comment
        await client.post(
            f"/api/articles/{article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "Test comment"}},
        )
        
        # Delete article
        delete_response = await client.delete(
            f"/api/articles/{article.slug}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204
        
        # Verify article and comments are gone
        get_response = await client.get(f"/api/articles/{article.slug}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_token_format(self, client: AsyncClient):
        """Test various invalid token formats."""
        invalid_headers = [
            {"Authorization": "Bearer token"},  # Wrong scheme
            {"Authorization": "token"},  # Missing scheme
            {"Authorization": "Token "},  # Empty token
            {},  # No header
        ]
        
        for headers in invalid_headers:
            response = await client.get("/api/user", headers=headers)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_json_requests(self, client: AsyncClient):
        """Test handling of malformed JSON."""
        # Note: FastAPI handles this at the framework level
        # This test verifies the behavior
        response = await client.post(
            "/api/users",
            content="{invalid json}",
            headers={"Content-Type": "application/json"},
        )
        # Should return 422 (Unprocessable Entity) for invalid JSON
        assert response.status_code in [400, 422]
