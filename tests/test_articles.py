"""Tests for article endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.articles.models import Article, Tag


class TestListArticles:
    """Tests for GET /api/articles endpoint."""

    @pytest.mark.asyncio
    async def test_list_articles_empty(self, client: AsyncClient):
        """Test listing articles when none exist."""
        response = await client.get("/api/articles")
        
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert "articlesCount" in data
        assert data["articles"] == []
        assert data["articlesCount"] == 0

    @pytest.mark.asyncio
    async def test_list_articles_with_articles(self, client: AsyncClient, test_article: Article):
        """Test listing articles with articles present."""
        response = await client.get("/api/articles")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articlesCount"] == 1
        assert data["articles"][0]["slug"] == test_article.slug

    @pytest.mark.asyncio
    async def test_list_articles_pagination(self, client: AsyncClient, db_session: AsyncSession, test_user: User):
        """Test article pagination."""
        # Create multiple articles
        for i in range(25):
            article = Article(
                slug=f"test-article-{i}",
                title=f"Test Article {i}",
                description=f"Description {i}",
                body=f"Body {i}",
                author_id=test_user.id,
            )
            db_session.add(article)
        await db_session.commit()
        
        # Get first page
        response = await client.get("/api/articles?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 10
        assert data["articlesCount"] == 25
        
        # Get second page
        response = await client.get("/api/articles?limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 10
        
        # Get third page
        response = await client.get("/api/articles?limit=10&offset=20")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 5

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_tag(self, client: AsyncClient, test_article_with_tags: Article):
        """Test filtering articles by tag."""
        response = await client.get("/api/articles?tag=python")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) >= 1
        assert "python" in data["articles"][0]["tagList"]

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_author(self, client: AsyncClient, test_article: Article, test_user: User):
        """Test filtering articles by author."""
        response = await client.get(f"/api/articles?author={test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) >= 1
        assert data["articles"][0]["author"]["username"] == test_user.username

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_favorited(self, client: AsyncClient, test_article: Article, test_user: User, auth_headers: dict, db_session: AsyncSession):
        """Test filtering articles by favorited user."""
        # Favorite the article first
        test_user.favorited_articles.append(test_article)
        await db_session.commit()
        
        response = await client.get(f"/api/articles?favorited={test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) >= 1

    @pytest.mark.asyncio
    async def test_list_articles_invalid_limit(self, client: AsyncClient):
        """Test with invalid limit parameter."""
        response = await client.get("/api/articles?limit=0")
        assert response.status_code == 422
        
        response = await client.get("/api/articles?limit=101")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_articles_invalid_offset(self, client: AsyncClient):
        """Test with invalid offset parameter."""
        response = await client.get("/api/articles?offset=-1")
        assert response.status_code == 422


class TestGetFeed:
    """Tests for GET /api/articles/feed endpoint."""

    @pytest.mark.asyncio
    async def test_get_feed_requires_auth(self, client: AsyncClient):
        """Test that feed requires authentication."""
        response = await client.get("/api/articles/feed")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_feed_empty(self, client: AsyncClient, auth_headers: dict):
        """Test feed when not following anyone."""
        response = await client.get("/api/articles/feed", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == []
        assert data["articlesCount"] == 0

    @pytest.mark.asyncio
    async def test_get_feed_with_followed_user_articles(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict, db_session: AsyncSession):
        """Test feed shows articles from followed users."""
        # Follow user2
        await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        # Create article by user2
        article = Article(
            slug="followed-user-article",
            title="Followed User Article",
            description="Description",
            body="Body",
            author_id=test_user2.id,
        )
        db_session.add(article)
        await db_session.commit()
        
        # Get feed
        response = await client.get("/api/articles/feed", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) >= 1
        assert data["articles"][0]["author"]["username"] == test_user2.username

    @pytest.mark.asyncio
    async def test_get_feed_pagination(self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict, db_session: AsyncSession):
        """Test feed pagination."""
        # Follow user2
        await client.post(f"/api/profiles/{test_user2.username}/follow", headers=auth_headers)
        
        # Create multiple articles
        for i in range(25):
            article = Article(
                slug=f"feed-article-{i}",
                title=f"Feed Article {i}",
                description=f"Description {i}",
                body=f"Body {i}",
                author_id=test_user2.id,
            )
            db_session.add(article)
        await db_session.commit()
        
        # Test pagination
        response = await client.get("/api/articles/feed?limit=10&offset=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 10
        assert data["articlesCount"] == 25


class TestCreateArticle:
    """Tests for POST /api/articles endpoint."""

    @pytest.mark.asyncio
    async def test_create_article_success(self, client: AsyncClient, auth_headers: dict, valid_article_data: dict):
        """Test successful article creation."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json=valid_article_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "article" in data
        assert data["article"]["title"] == valid_article_data["article"]["title"]
        assert data["article"]["description"] == valid_article_data["article"]["description"]
        assert data["article"]["body"] == valid_article_data["article"]["body"]
        assert "slug" in data["article"]
        assert "createdAt" in data["article"]
        assert "updatedAt" in data["article"]
        assert "author" in data["article"]

    @pytest.mark.asyncio
    async def test_create_article_with_tags(self, client: AsyncClient, auth_headers: dict, valid_article_data: dict):
        """Test creating article with tags."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json=valid_article_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert set(data["article"]["tagList"]) == set(valid_article_data["article"]["tagList"])

    @pytest.mark.asyncio
    async def test_create_article_no_auth(self, client: AsyncClient, valid_article_data: dict):
        """Test creating article without authentication."""
        response = await client.post("/api/articles", json=valid_article_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_article_missing_title(self, client: AsyncClient, auth_headers: dict):
        """Test creating article without title."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "description": "Description",
                    "body": "Body"
                }
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_article_missing_description(self, client: AsyncClient, auth_headers: dict):
        """Test creating article without description."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Title",
                    "body": "Body"
                }
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_article_missing_body(self, client: AsyncClient, auth_headers: dict):
        """Test creating article without body."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Title",
                    "description": "Description"
                }
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_article_slug_generation(self, client: AsyncClient, auth_headers: dict, valid_article_data: dict):
        """Test that slugs are generated uniquely."""
        # Create first article
        response1 = await client.post(
            "/api/articles",
            headers=auth_headers,
            json=valid_article_data
        )
        slug1 = response1.json()["article"]["slug"]
        
        # Create second article with same title
        response2 = await client.post(
            "/api/articles",
            headers=auth_headers,
            json=valid_article_data
        )
        slug2 = response2.json()["article"]["slug"]
        
        # Slugs should be different
        assert slug1 != slug2

    @pytest.mark.asyncio
    async def test_create_article_too_many_tags(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with too many tags."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Test",
                    "description": "Test",
                    "body": "Test",
                    "tagList": [f"tag{i}" for i in range(25)]  # More than MAX_TAGS_PER_ARTICLE
                }
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_article_xss_prevention(self, client: AsyncClient, auth_headers: dict):
        """Test XSS prevention in article content."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "<script>alert('xss')</script>",
                    "description": "<img src=x onerror=alert('xss')>",
                    "body": "<iframe src='evil.com'></iframe>",
                    "tagList": []
                }
            }
        )
        
        assert response.status_code in [201, 422]
        if response.status_code == 201:
            data = response.json()
            # Content should be sanitized
            assert "<script>" not in data["article"]["title"]
            assert "<img" not in data["article"]["description"]
            assert "<iframe" not in data["article"]["body"]


class TestGetArticle:
    """Tests for GET /api/articles/{slug} endpoint."""

    @pytest.mark.asyncio
    async def test_get_article_success(self, client: AsyncClient, test_article: Article):
        """Test getting an article."""
        response = await client.get(f"/api/articles/{test_article.slug}")
        
        assert response.status_code == 200
        data = response.json()
        assert "article" in data
        assert data["article"]["slug"] == test_article.slug
        assert data["article"]["title"] == test_article.title

    @pytest.mark.asyncio
    async def test_get_article_not_found(self, client: AsyncClient):
        """Test getting non-existent article."""
        response = await client.get("/api/articles/nonexistent-slug")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_article_with_auth(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test getting article while authenticated."""
        response = await client.get(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "favorited" in data["article"]
        assert "favoritesCount" in data["article"]


class TestUpdateArticle:
    """Tests for PUT /api/articles/{slug} endpoint."""

    @pytest.mark.asyncio
    async def test_update_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test successfully updating an article."""
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated Title",
                    "description": "Updated description",
                    "body": "Updated body"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["title"] == "Updated Title"
        assert data["article"]["description"] == "Updated description"
        assert data["article"]["body"] == "Updated body"

    @pytest.mark.asyncio
    async def test_update_article_partial(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test partially updating an article."""
        original_body = test_article.body
        
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers,
            json={
                "article": {
                    "title": "New Title Only"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["title"] == "New Title Only"
        # Body should remain unchanged
        assert data["article"]["body"] == original_body

    @pytest.mark.asyncio
    async def test_update_article_not_owner(self, client: AsyncClient, test_article: Article, auth_headers2: dict):
        """Test updating article by non-owner."""
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers2,
            json={
                "article": {
                    "title": "Updated Title"
                }
            }
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test updating article without authentication."""
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            json={
                "article": {
                    "title": "Updated Title"
                }
            }
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test updating non-existent article."""
        response = await client.put(
            "/api/articles/nonexistent-slug",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated Title"
                }
            }
        )
        assert response.status_code == 404


class TestDeleteArticle:
    """Tests for DELETE /api/articles/{slug} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test successfully deleting an article."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify article is deleted
        get_response = await client.get(f"/api/articles/{test_article.slug}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_article_not_owner(self, client: AsyncClient, test_article: Article, auth_headers2: dict):
        """Test deleting article by non-owner."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers2
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test deleting article without authentication."""
        response = await client.delete(f"/api/articles/{test_article.slug}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test deleting non-existent article."""
        response = await client.delete(
            "/api/articles/nonexistent-slug",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestFavoriteArticle:
    """Tests for POST /api/articles/{slug}/favorite endpoint."""

    @pytest.mark.asyncio
    async def test_favorite_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test successfully favoriting an article."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is True
        assert data["article"]["favoritesCount"] == 1

    @pytest.mark.asyncio
    async def test_favorite_article_already_favorited(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test favoriting an already favorited article (idempotent)."""
        # Favorite first time
        await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        # Favorite again
        response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is True
        assert data["article"]["favoritesCount"] == 1

    @pytest.mark.asyncio
    async def test_favorite_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test favoriting without authentication."""
        response = await client.post(f"/api/articles/{test_article.slug}/favorite")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_favorite_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test favoriting non-existent article."""
        response = await client.post(
            "/api/articles/nonexistent-slug/favorite",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestUnfavoriteArticle:
    """Tests for DELETE /api/articles/{slug}/favorite endpoint."""

    @pytest.mark.asyncio
    async def test_unfavorite_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test successfully unfavoriting an article."""
        # First favorite
        await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        # Then unfavorite
        response = await client.delete(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is False
        assert data["article"]["favoritesCount"] == 0

    @pytest.mark.asyncio
    async def test_unfavorite_article_not_favorited(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test unfavoriting an article that's not favorited (idempotent)."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is False

    @pytest.mark.asyncio
    async def test_unfavorite_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test unfavoriting without authentication."""
        response = await client.delete(f"/api/articles/{test_article.slug}/favorite")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unfavorite_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test unfavoriting non-existent article."""
        response = await client.delete(
            "/api/articles/nonexistent-slug/favorite",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestTags:
    """Tests for GET /api/tags endpoint."""

    @pytest.mark.asyncio
    async def test_get_tags_empty(self, client: AsyncClient):
        """Test getting tags when none exist."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert data["tags"] == []

    @pytest.mark.asyncio
    async def test_get_tags_with_tags(self, client: AsyncClient, test_article_with_tags: Article):
        """Test getting tags when they exist."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) >= 2
        assert "python" in data["tags"]
        assert "testing" in data["tags"]

    @pytest.mark.asyncio
    async def test_get_tags_no_duplicates(self, client: AsyncClient, db_session: AsyncSession, test_user: User):
        """Test that tags list contains no duplicates."""
        # Create tag
        tag = Tag(tag="duplicate", slug="duplicate")
        db_session.add(tag)
        await db_session.flush()
        
        # Create multiple articles with the same tag
        for i in range(3):
            article = Article(
                slug=f"article-{i}",
                title=f"Article {i}",
                description="Description",
                body="Body",
                author_id=test_user.id,
                tags=[tag]
            )
            db_session.add(article)
        await db_session.commit()
        
        # Get tags
        response = await client.get("/api/tags")
        data = response.json()
        
        # Count occurrences of "duplicate" tag
        duplicate_count = data["tags"].count("duplicate")
        assert duplicate_count == 1
