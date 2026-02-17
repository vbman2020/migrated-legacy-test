"""Tests for article endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.articles.models import Article


@pytest_asyncio.fixture
async def test_article(db_session: AsyncSession, test_user: User) -> Article:
    """Create a test article."""
    from app.articles.service import create_article
    from app.articles.schemas import ArticleCreate
    
    article_data = ArticleCreate(
        title="Test Article",
        description="Test description",
        body="Test body content",
        tag_list=["test", "pytest"]
    )
    
    article = await create_article(db_session, article_data, test_user)
    return article


class TestListArticles:
    """Tests for GET /api/articles."""
    
    @pytest.mark.asyncio
    async def test_list_articles_empty(self, client: AsyncClient):
        """Test listing articles when none exist."""
        response = await client.get("/api/articles")
        
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == []
        assert data["articlesCount"] == 0
    
    @pytest.mark.asyncio
    async def test_list_articles_with_articles(self, client: AsyncClient, test_article: Article):
        """Test listing articles returns created articles."""
        response = await client.get("/api/articles")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articlesCount"] == 1
        assert data["articles"][0]["title"] == "Test Article"
    
    @pytest.mark.asyncio
    async def test_list_articles_pagination(self, client: AsyncClient, test_article: Article):
        """Test article list pagination."""
        response = await client.get("/api/articles?limit=1&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) <= 1
    
    @pytest.mark.asyncio
    async def test_list_articles_filter_by_author(self, client: AsyncClient, test_article: Article):
        """Test filtering articles by author."""
        response = await client.get("/api/articles?author=testuser")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["author"]["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_list_articles_filter_by_tag(self, client: AsyncClient, test_article: Article):
        """Test filtering articles by tag."""
        response = await client.get("/api/articles?tag=test")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert "test" in data["articles"][0]["tagList"]
    
    @pytest.mark.asyncio
    async def test_list_articles_filter_by_favorited(self, client: AsyncClient, test_article: Article, test_user2: User, auth_headers2: dict):
        """Test filtering articles by favorited user."""
        # Favorite the article
        await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers2
        )
        
        response = await client.get("/api/articles?favorited=testuser2")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1


class TestGetArticlesFeed:
    """Tests for GET /api/articles/feed."""
    
    @pytest.mark.asyncio
    async def test_get_feed_no_auth(self, client: AsyncClient):
        """Test getting feed without authentication fails."""
        response = await client.get("/api/articles/feed")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_feed_empty(self, client: AsyncClient, auth_headers: dict):
        """Test getting feed when not following anyone."""
        response = await client.get("/api/articles/feed", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == []
        assert data["articlesCount"] == 0
    
    @pytest.mark.asyncio
    async def test_get_feed_with_followed_articles(self, client: AsyncClient, test_user: User, test_user2: User, test_article: Article, auth_headers2: dict):
        """Test getting feed includes articles from followed users."""
        # User2 follows User1
        await client.post(
            f"/api/profiles/{test_user.username}/follow",
            headers=auth_headers2
        )
        
        # User2 gets feed
        response = await client.get("/api/articles/feed", headers=auth_headers2)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["author"]["username"] == "testuser"


class TestCreateArticle:
    """Tests for POST /api/articles."""
    
    @pytest.mark.asyncio
    async def test_create_article_success(self, client: AsyncClient, auth_headers: dict):
        """Test successfully creating an article."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "New Article",
                    "description": "Article description",
                    "body": "Article body content",
                    "tagList": ["tag1", "tag2"]
                }
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "article" in data
        assert data["article"]["title"] == "New Article"
        assert "slug" in data["article"]
        assert len(data["article"]["tagList"]) == 2
    
    @pytest.mark.asyncio
    async def test_create_article_no_auth(self, client: AsyncClient):
        """Test creating article without authentication fails."""
        response = await client.post(
            "/api/articles",
            json={
                "article": {
                    "title": "New Article",
                    "description": "Article description",
                    "body": "Article body content"
                }
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_create_article_missing_fields(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with missing required fields fails."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "New Article"
                    # Missing description and body
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_article_empty_title(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with empty title fails."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "   ",
                    "description": "Description",
                    "body": "Body"
                }
            }
        )
        
        assert response.status_code == 422


class TestGetArticle:
    """Tests for GET /api/articles/{slug}."""
    
    @pytest.mark.asyncio
    async def test_get_article_success(self, client: AsyncClient, test_article: Article):
        """Test successfully getting an article."""
        response = await client.get(f"/api/articles/{test_article.slug}")
        
        assert response.status_code == 200
        data = response.json()
        assert "article" in data
        assert data["article"]["title"] == "Test Article"
        assert data["article"]["slug"] == test_article.slug
    
    @pytest.mark.asyncio
    async def test_get_article_nonexistent(self, client: AsyncClient):
        """Test getting non-existent article returns 404."""
        response = await client.get("/api/articles/nonexistent-slug")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_article_includes_author(self, client: AsyncClient, test_article: Article):
        """Test article response includes author information."""
        response = await client.get(f"/api/articles/{test_article.slug}")
        
        assert response.status_code == 200
        data = response.json()
        assert "author" in data["article"]
        assert data["article"]["author"]["username"] == "testuser"


class TestUpdateArticle:
    """Tests for PUT /api/articles/{slug}."""
    
    @pytest.mark.asyncio
    async def test_update_article_title(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test updating article title."""
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated Title"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["title"] == "Updated Title"
    
    @pytest.mark.asyncio
    async def test_update_article_body(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test updating article body."""
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers,
            json={
                "article": {
                    "body": "Updated body content"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["body"] == "Updated body content"
    
    @pytest.mark.asyncio
    async def test_update_article_not_author(self, client: AsyncClient, test_article: Article, auth_headers2: dict):
        """Test updating article by non-author fails."""
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
        """Test updating article without authentication fails."""
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
    async def test_update_article_nonexistent(self, client: AsyncClient, auth_headers: dict):
        """Test updating non-existent article returns 404."""
        response = await client.put(
            "/api/articles/nonexistent",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated Title"
                }
            }
        )
        
        assert response.status_code == 404


class TestDeleteArticle:
    """Tests for DELETE /api/articles/{slug}."""
    
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
    async def test_delete_article_not_author(self, client: AsyncClient, test_article: Article, auth_headers2: dict):
        """Test deleting article by non-author fails."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers2
        )
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_delete_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test deleting article without authentication fails."""
        response = await client.delete(f"/api/articles/{test_article.slug}")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_delete_article_nonexistent(self, client: AsyncClient, auth_headers: dict):
        """Test deleting non-existent article returns 404."""
        response = await client.delete(
            "/api/articles/nonexistent",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestFavoriteArticle:
    """Tests for POST /api/articles/{slug}/favorite."""
    
    @pytest.mark.asyncio
    async def test_favorite_article_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test successfully favoriting an article."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["article"]["favorited"] is True
        assert data["article"]["favoritesCount"] >= 1
    
    @pytest.mark.asyncio
    async def test_favorite_article_already_favorited(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test favoriting an already favorited article (idempotent)."""
        # Favorite once
        await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        # Favorite again
        response = await client.post(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["article"]["favorited"] is True
    
    @pytest.mark.asyncio
    async def test_favorite_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test favoriting without authentication fails."""
        response = await client.post(f"/api/articles/{test_article.slug}/favorite")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_favorite_nonexistent_article(self, client: AsyncClient, auth_headers: dict):
        """Test favoriting non-existent article returns 404."""
        response = await client.post(
            "/api/articles/nonexistent/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestUnfavoriteArticle:
    """Tests for DELETE /api/articles/{slug}/favorite."""
    
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
    
    @pytest.mark.asyncio
    async def test_unfavorite_article_not_favorited(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test unfavoriting a non-favorited article (idempotent)."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/favorite",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is False
    
    @pytest.mark.asyncio
    async def test_unfavorite_article_no_auth(self, client: AsyncClient, test_article: Article):
        """Test unfavoriting without authentication fails."""
        response = await client.delete(f"/api/articles/{test_article.slug}/favorite")
        
        assert response.status_code == 401
