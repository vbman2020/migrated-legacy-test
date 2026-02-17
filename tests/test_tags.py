"""Tests for tag endpoints."""
import pytest
from httpx import AsyncClient

from app.articles.models import Tag


class TestGetTags:
    """Tests for GET /api/tags."""

    @pytest.mark.asyncio
    async def test_get_tags_empty(self, client: AsyncClient):
        """Test getting tags when none exist."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    @pytest.mark.asyncio
    async def test_get_tags_with_data(self, client: AsyncClient, test_tags: list[Tag]):
        """Test getting tags when tags exist."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert len(data["tags"]) >= 3
        assert "python" in data["tags"]
        assert "fastapi" in data["tags"]
        assert "testing" in data["tags"]

    @pytest.mark.asyncio
    async def test_get_tags_no_auth_required(self, client: AsyncClient, test_tags: list[Tag]):
        """Test that getting tags doesn't require authentication."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_tags_returns_unique(self, client: AsyncClient, test_article_with_tags):
        """Test that tags endpoint returns unique tags."""
        response = await client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        tags_list = data["tags"]
        
        # Check no duplicates
        assert len(tags_list) == len(set(tags_list))
