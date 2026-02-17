"""Tests for article endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles.models import Article, Tag, Comment
from app.auth.models import User


class TestCreateArticle:
    """Tests for POST /api/articles."""

    @pytest.mark.asyncio
    async def test_create_article_success(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """Test successful article creation."""
        payload = {
            "article": {
                "title": "Test Article Title",
                "description": "Test description",
                "body": "Test body content that is longer",
                "tagList": ["python", "testing"]
            }
        }
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert "article" in data
        assert data["article"]["title"] == "Test Article Title"
        assert data["article"]["description"] == "Test description"
        assert data["article"]["body"] == "Test body content that is longer"
        assert "slug" in data["article"]
        assert set(data["article"]["tagList"]) == {"python", "testing"}
        assert data["article"]["favorited"] is False
        assert data["article"]["favoritesCount"] == 0
        assert "author" in data["article"]

    @pytest.mark.asyncio
    async def test_create_article_without_tags(self, client: AsyncClient, auth_headers: dict):
        """Test creating article without tags."""
        payload = {
            "article": {
                "title": "Test Article",
                "description": "Test description",
                "body": "Test body"
            }
        }
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["article"]["tagList"] == []

    @pytest.mark.asyncio
    async def test_create_article_unauthorized(self, client: AsyncClient):
        """Test creating article without authentication."""
        payload = {
            "article": {
                "title": "Test Article",
                "description": "Test description",
                "body": "Test body"
            }
        }
        
        response = await client.post("/api/articles", json=payload)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_article_missing_fields(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with missing required fields."""
        payload = {"article": {"title": "Test Article"}}
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_article_empty_title(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with empty title."""
        payload = {
            "article": {
                "title": "   ",
                "description": "Test description",
                "body": "Test body"
            }
        }
        
        response = await client.post("/api/articles", json=payload, headers=auth_headers)
        
        assert response.status_code == 422


class TestListArticles:
    """Tests for GET /api/articles."""

    @pytest.mark.asyncio
    async def test_list_articles_default(self, client: AsyncClient, test_article: Article):
        """Test listing articles with default parameters."""
        response = await client.get("/api/articles")
        
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert "articlesCount" in data
        assert data["articlesCount"] >= 1
        assert len(data["articles"]) >= 1

    @pytest.mark.asyncio
    async def test_list_articles_with_limit(self, client: AsyncClient, test_article: Article):
        """Test listing articles with limit parameter."""
        response = await client.get("/api/articles?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) <= 10

    @pytest.mark.asyncio
    async def test_list_articles_with_offset(self, client: AsyncClient, test_article: Article):
        """Test listing articles with offset parameter."""
        response = await client.get("/api/articles?offset=0")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_tag(self, client: AsyncClient, test_article_with_tags: Article):
        """Test filtering articles by tag."""
        response = await client.get("/api/articles?tag=python")
        
        assert response.status_code == 200
        data = response.json()
        for article in data["articles"]:
            assert "python" in article["tagList"]

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_author(self, client: AsyncClient, test_article: Article, test_user: User):
        """Test filtering articles by author."""
        response = await client.get(f"/api/articles?author={test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        for article in data["articles"]:
            assert article["author"]["username"] == test_user.username

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_favorited(self, client: AsyncClient, test_user: User):
        """Test filtering articles by favorited user."""
        response = await client.get(f"/api/articles?favorited={test_user.username}")
        
        assert response.status_code == 200
        data = response.json()
        # Should only show articles favorited by the user

    @pytest.mark.asyncio
    async def test_list_articles_invalid_limit(self, client: AsyncClient):
        """Test listing articles with invalid limit."""
        response = await client.get("/api/articles?limit=0")
        
        assert response.status_code == 422


class TestGetArticleFeed:
    """Tests for GET /api/articles/feed."""

    @pytest.mark.asyncio
    async def test_get_feed_success(self, client: AsyncClient, auth_headers: dict):
        """Test getting article feed."""
        response = await client.get("/api/articles/feed", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert "articlesCount" in data

    @pytest.mark.asyncio
    async def test_get_feed_unauthorized(self, client: AsyncClient):
        """Test getting feed without authentication."""
        response = await client.get("/api/articles/feed")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_feed_with_pagination(self, client: AsyncClient, auth_headers: dict):
        """Test getting feed with pagination."""
        response = await client.get("/api/articles/feed?limit=5&offset=0", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) <= 5


class TestGetArticle:
    """Tests for GET /api/articles/{slug}."""

    @pytest.mark.asyncio
    async def test_get_article_success(self, client: AsyncClient, test_article: Article):
        """Test getting article by slug."""
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
        assert "not exist" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_article_authenticated(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test getting article as authenticated user."""
        response = await client.get(f"/api/articles/{test_article.slug}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "favorited" in data["article"]


class TestUpdateArticle:
    """Tests for PUT /api/articles/{slug}."""

    @pytest.mark.asyncio
    async def test_update_article_title(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test updating article title."""
        payload = {
            "article": {
                "title": "Updated Title"
            }
        }
        
        response = await client.put(f"/api/articles/{test_article.slug}", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["title"] == "Updated Title"
        # Slug should be regenerated
        assert data["article"]["slug"] != test_article.slug

    @pytest.mark.asyncio
    async def test_update_article_body(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test updating article body."""
        payload = {
            "article": {
                "body": "Updated body content"
            }
        }
        
        response = await client.put(f"/api/articles/{test_article.slug}", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["body"] == "Updated body content"

    @pytest.mark.asyncio
    async def test_update_article_unauthorized(self, client: AsyncClient, test_article: Article):
        """Test updating article without authentication."""
        payload = {"article": {"title": "Updated Title"}}
        
        response = await client.put(f"/api/articles/{test_article.slug}", json=payload)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_article_not_author(self, client: AsyncClient, test_article: Article, auth_headers2: dict):
        """Test updating article by non-author."""
        payload = {"article": {"title": "Updated Title"}}
        
        response = await client.put(f"/api/articles/{test_article.slug}", json=payload, headers=auth_headers2)
        
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test updating non-existent article."""
        payload = {"article": {"title": "Updated Title"}}
        
        response = await client.put("/api/articles/nonexistent-slug", json=payload, headers=auth_headers)
        
        assert response.status_code == 404


class TestDeleteArticle:
    """Tests for DELETE /api/articles/{slug}."""

    @pytest.mark.asyncio
    async def test_delete_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict, db_session: AsyncSession):
        """Test successful article deletion."""
        slug = test_article.slug
        
        response = await client.delete(f"/api/articles/{slug}", headers=auth_headers)
        
        assert response.status_code == 204
        
        # Verify article is deleted
        result = await db_session.execute(select(Article).where(Article.slug == slug))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_article_unauthorized(self, client: AsyncClient, test_article: Article):
        """Test deleting article without authentication."""
        response = await client.delete(f"/api/articles/{test_article.slug}")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_article_not_author(self, client: AsyncClient, test_article: Article, auth_headers2: dict):
        """Test deleting article by non-author."""
        response = await client.delete(f"/api/articles/{test_article.slug}", headers=auth_headers2)
        
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test deleting non-existent article."""
        response = await client.delete("/api/articles/nonexistent-slug", headers=auth_headers)
        
        assert response.status_code == 404


class TestFavoriteArticle:
    """Tests for POST /api/articles/{slug}/favorite."""

    @pytest.mark.asyncio
    async def test_favorite_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test favoriting an article."""
        response = await client.post(f"/api/articles/{test_article.slug}/favorite", headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["article"]["favorited"] is True
        assert data["article"]["favoritesCount"] == 1

    @pytest.mark.asyncio
    async def test_favorite_article_twice(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test favoriting an article twice (idempotent)."""
        # First favorite
        await client.post(f"/api/articles/{test_article.slug}/favorite", headers=auth_headers)
        
        # Second favorite
        response = await client.post(f"/api/articles/{test_article.slug}/favorite", headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["article"]["favorited"] is True
        assert data["article"]["favoritesCount"] == 1  # Should not increase

    @pytest.mark.asyncio
    async def test_favorite_article_unauthorized(self, client: AsyncClient, test_article: Article):
        """Test favoriting article without authentication."""
        response = await client.post(f"/api/articles/{test_article.slug}/favorite")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_favorite_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test favoriting non-existent article."""
        response = await client.post("/api/articles/nonexistent-slug/favorite", headers=auth_headers)
        
        assert response.status_code == 404


class TestUnfavoriteArticle:
    """Tests for DELETE /api/articles/{slug}/favorite."""

    @pytest.mark.asyncio
    async def test_unfavorite_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test unfavoriting an article."""
        # First favorite
        await client.post(f"/api/articles/{test_article.slug}/favorite", headers=auth_headers)
        
        # Then unfavorite
        response = await client.delete(f"/api/articles/{test_article.slug}/favorite", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is False
        assert data["article"]["favoritesCount"] == 0

    @pytest.mark.asyncio
    async def test_unfavorite_article_not_favorited(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test unfavoriting an article that wasn't favorited."""
        response = await client.delete(f"/api/articles/{test_article.slug}/favorite", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is False

    @pytest.mark.asyncio
    async def test_unfavorite_article_unauthorized(self, client: AsyncClient, test_article: Article):
        """Test unfavoriting article without authentication."""
        response = await client.delete(f"/api/articles/{test_article.slug}/favorite")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unfavorite_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test unfavoriting non-existent article."""
        response = await client.delete("/api/articles/nonexistent-slug/favorite", headers=auth_headers)
        
        assert response.status_code == 404
