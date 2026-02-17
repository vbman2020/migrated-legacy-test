"""Tests for tags endpoint."""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.articles.models import Article


@pytest_asyncio.fixture
async def test_articles_with_tags(db_session: AsyncSession, test_user: User) -> list[Article]:
    """Create test articles with various tags."""
    from app.articles.service import create_article
    from app.articles.schemas import ArticleCreate
    
    articles = []
    
    article1_data = ArticleCreate(
        title="Article 1",
        description="Description 1",
        body="Body 1",
        tag_list=["python", "fastapi"]
    )
    article1 = await create_article(db_session, article1_data, test_user)
    articles.append(article1)
    
    article2_data = ArticleCreate(
        title="Article 2",
        description="Description 2",
        body="Body 2",
        tag_list=["javascript", "react"]
    )
    article2 = await create_article(db_session, article2_data, test_user)
    articles.append(article2)
    
    article3_data = ArticleCreate(
        title="Article 3",
        description="Description 3",
        body="Body 3",
        tag_list=["python", "django"]
    )
    article3 = await create_article(db_session, article3_data, test_user)
    articles.append(article3)
    
    return articles


class TestGetTags:
    """Tests for GET /api/tags."""
    
    @pytest.mark.asyncio
    async def test_get_tags_empty(self, client: AsyncClient):
        """Test getting tags when none exist."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == []
    
    @pytest.mark.asyncio
    async def test_get_tags_with_articles(self, client: AsyncClient, test_articles_with_tags: list[Article]):
        """Test getting tags returns all unique tags."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) >= 4  # python, fastapi, javascript, react, django
        assert "python" in data["tags"]
        assert "fastapi" in data["tags"]
        assert "javascript" in data["tags"]
        assert "react" in data["tags"]
    
    @pytest.mark.asyncio
    async def test_get_tags_no_duplicates(self, client: AsyncClient, test_articles_with_tags: list[Article]):
        """Test tags list doesn't contain duplicates."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        tags = data["tags"]
        assert len(tags) == len(set(tags))  # No duplicates
    
    @pytest.mark.asyncio
    async def test_get_tags_no_auth_required(self, client: AsyncClient, test_articles_with_tags: list[Article]):
        """Test getting tags doesn't require authentication."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        assert "tags" in response.json()
