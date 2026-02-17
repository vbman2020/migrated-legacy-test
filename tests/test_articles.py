"""Tests for articles endpoints.

Tests CRUD operations, favorites, feed, comments, and tags.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.articles.models import Article, Tag
from app.articles.service import ArticleService


class TestListArticles:
    """Test list articles endpoint GET /api/articles."""

    @pytest.mark.asyncio
    async def test_list_articles_empty(self, client: AsyncClient):
        """Test listing articles when none exist."""
        response = await client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == []
        assert data["articlesCount"] == 0

    @pytest.mark.asyncio
    async def test_list_articles_with_data(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test listing articles with data."""
        # Create test article
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        article_data = ArticleCreateSchema(
            title="Test Article",
            description="Test description",
            body="Test body",
            tagList=["test"],
        )
        await service.create_article(article_data, test_user)
        await db_session.commit()
        
        response = await client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articlesCount"] == 1
        assert data["articles"][0]["title"] == "Test Article"

    @pytest.mark.asyncio
    async def test_list_articles_pagination(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test article pagination."""
        # Create multiple articles
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        for i in range(5):
            article_data = ArticleCreateSchema(
                title=f"Test Article {i}",
                description=f"Test description {i}",
                body=f"Test body {i}",
                tagList=[],
            )
            await service.create_article(article_data, test_user)
        await db_session.commit()
        
        # Test limit
        response = await client.get("/api/articles?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 2
        assert data["articlesCount"] == 5
        
        # Test offset
        response = await client.get("/api/articles?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 2

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_tag(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test filtering articles by tag."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        
        # Create articles with different tags
        await service.create_article(
            ArticleCreateSchema(
                title="Article 1",
                description="Desc 1",
                body="Body 1",
                tagList=["python"],
            ),
            test_user,
        )
        await service.create_article(
            ArticleCreateSchema(
                title="Article 2",
                description="Desc 2",
                body="Body 2",
                tagList=["javascript"],
            ),
            test_user,
        )
        await db_session.commit()
        
        response = await client.get("/api/articles?tag=python")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["title"] == "Article 1"

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_author(
        self, client: AsyncClient, test_user: User, test_user2: User, db_session: AsyncSession
    ):
        """Test filtering articles by author."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        
        await service.create_article(
            ArticleCreateSchema(
                title="Article by user 1",
                description="Desc",
                body="Body",
                tagList=[],
            ),
            test_user,
        )
        await service.create_article(
            ArticleCreateSchema(
                title="Article by user 2",
                description="Desc",
                body="Body",
                tagList=[],
            ),
            test_user2,
        )
        await db_session.commit()
        
        response = await client.get(f"/api/articles?author={test_user.username}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["title"] == "Article by user 1"

    @pytest.mark.asyncio
    async def test_list_articles_filter_by_favorited(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test filtering articles by who favorited them."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        
        article = await service.create_article(
            ArticleCreateSchema(
                title="Test Article",
                description="Desc",
                body="Body",
                tagList=[],
            ),
            test_user,
        )
        await db_session.commit()
        
        # Favorite the article
        await client.post(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        
        response = await client.get(f"/api/articles?favorited={test_user.username}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["slug"] == article.slug


class TestCreateArticle:
    """Test create article endpoint POST /api/articles."""

    @pytest.mark.asyncio
    async def test_create_article_success(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test successful article creation."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "How to train your dragon",
                    "description": "Ever wonder how?",
                    "body": "You have to believe",
                    "tagList": ["dragons", "training"],
                }
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["article"]["title"] == "How to train your dragon"
        assert data["article"]["description"] == "Ever wonder how?"
        assert data["article"]["body"] == "You have to believe"
        assert set(data["article"]["tagList"]) == {"dragons", "training"}
        assert "slug" in data["article"]
        assert data["article"]["author"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_create_article_no_auth(self, client: AsyncClient):
        """Test creating article without auth fails."""
        response = await client.post(
            "/api/articles",
            json={
                "article": {
                    "title": "Test",
                    "description": "Test",
                    "body": "Test",
                }
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_article_missing_fields(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with missing fields fails."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Test",
                }
            },
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
                    "title": "",
                    "description": "Test",
                    "body": "Test",
                }
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_article_duplicate_tags(self, client: AsyncClient, auth_headers: dict):
        """Test creating article with duplicate tags removes duplicates."""
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Test",
                    "description": "Test",
                    "body": "Test",
                    "tagList": ["python", "Python", "PYTHON"],
                }
            },
        )
        assert response.status_code == 201
        data = response.json()
        # Should deduplicate case-insensitive
        assert len(data["article"]["tagList"]) == 1


class TestGetArticle:
    """Test get article endpoint GET /api/articles/{slug}."""

    @pytest.mark.asyncio
    async def test_get_article_success(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test getting article by slug."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        article = await service.create_article(
            ArticleCreateSchema(
                title="Test Article",
                description="Test description",
                body="Test body",
                tagList=[],
            ),
            test_user,
        )
        await db_session.commit()
        
        response = await client.get(f"/api/articles/{article.slug}")
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["slug"] == article.slug
        assert data["article"]["title"] == "Test Article"

    @pytest.mark.asyncio
    async def test_get_article_not_found(self, client: AsyncClient):
        """Test getting nonexistent article returns 404."""
        response = await client.get("/api/articles/nonexistent-slug")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_article_favorited_flag(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test favorited flag is set correctly."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        article = await service.create_article(
            ArticleCreateSchema(
                title="Test Article",
                description="Test",
                body="Test",
                tagList=[],
            ),
            test_user,
        )
        await db_session.commit()
        
        # Check not favorited
        response = await client.get(
            f"/api/articles/{article.slug}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["article"]["favorited"] is False
        
        # Favorite article
        await client.post(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        
        # Check favorited
        response = await client.get(
            f"/api/articles/{article.slug}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["article"]["favorited"] is True


class TestUpdateArticle:
    """Test update article endpoint PUT /api/articles/{slug}."""

    @pytest.mark.asyncio
    async def test_update_article_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test updating article."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        article = await service.create_article(
            ArticleCreateSchema(
                title="Original Title",
                description="Original description",
                body="Original body",
                tagList=[],
            ),
            test_user,
        )
        await db_session.commit()
        
        response = await client.put(
            f"/api/articles/{article.slug}",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated Title",
                    "description": "Updated description",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["title"] == "Updated Title"
        assert data["article"]["description"] == "Updated description"
        assert data["article"]["body"] == "Original body"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_article_not_owner(
        self, client: AsyncClient, test_user: User, test_user2: User, auth_headers2: dict, db_session: AsyncSession
    ):
        """Test updating article by non-owner fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.put(
            f"/api/articles/{article.slug}",
            headers=auth_headers2,
            json={
                "article": {
                    "title": "Hacked",
                }
            },
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_article_no_auth(self, client: AsyncClient, test_user: User, db_session: AsyncSession):
        """Test updating article without auth fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.put(
            f"/api/articles/{article.slug}",
            json={
                "article": {
                    "title": "Updated",
                }
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_article_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test updating nonexistent article returns 404."""
        response = await client.put(
            "/api/articles/nonexistent",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Updated",
                }
            },
        )
        assert response.status_code == 404


class TestDeleteArticle:
    """Test delete article endpoint DELETE /api/articles/{slug}."""

    @pytest.mark.asyncio
    async def test_delete_article_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test deleting article."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.delete(
            f"/api/articles/{article.slug}",
            headers=auth_headers,
        )
        assert response.status_code == 204
        
        # Verify article is deleted
        get_response = await client.get(f"/api/articles/{article.slug}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_article_not_owner(
        self, client: AsyncClient, test_user: User, auth_headers2: dict, db_session: AsyncSession
    ):
        """Test deleting article by non-owner fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.delete(
            f"/api/articles/{article.slug}",
            headers=auth_headers2,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_article_no_auth(self, client: AsyncClient, test_user: User, db_session: AsyncSession):
        """Test deleting article without auth fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.delete(f"/api/articles/{article.slug}")
        assert response.status_code == 401


class TestFavoriteArticle:
    """Test favorite/unfavorite article endpoints."""

    @pytest.mark.asyncio
    async def test_favorite_article_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test favoriting article."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.post(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is True
        assert data["article"]["favoritesCount"] == 1

    @pytest.mark.asyncio
    async def test_unfavorite_article_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test unfavoriting article."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        # First favorite
        await client.post(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        
        # Then unfavorite
        response = await client.delete(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["favorited"] is False
        assert data["article"]["favoritesCount"] == 0

    @pytest.mark.asyncio
    async def test_favorite_article_no_auth(self, client: AsyncClient, test_user: User, db_session: AsyncSession):
        """Test favoriting without auth fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.post(f"/api/articles/{article.slug}/favorite")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_favorite_article_twice_idempotent(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test favoriting article twice is idempotent."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        # Favorite twice
        response1 = await client.post(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        response2 = await client.post(
            f"/api/articles/{article.slug}/favorite",
            headers=auth_headers,
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response2.json()["article"]["favoritesCount"] == 1


class TestComments:
    """Test comment endpoints."""

    @pytest.mark.asyncio
    async def test_add_comment_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test adding comment to article."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.post(
            f"/api/articles/{article.slug}/comments",
            headers=auth_headers,
            json={
                "comment": {
                    "body": "Great article!",
                }
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["comment"]["body"] == "Great article!"
        assert data["comment"]["author"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_comments(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test getting comments for article."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        # Add comments
        await client.post(
            f"/api/articles/{article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "Comment 1"}},
        )
        await client.post(
            f"/api/articles/{article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "Comment 2"}},
        )
        
        response = await client.get(f"/api/articles/{article.slug}/comments")
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 2

    @pytest.mark.asyncio
    async def test_delete_comment_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test deleting comment."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        add_response = await client.post(
            f"/api/articles/{article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "Test comment"}},
        )
        comment_id = add_response.json()["comment"]["id"]
        
        # Delete comment
        response = await client.delete(
            f"/api/articles/{article.slug}/comments/{comment_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204
        
        # Verify comment is deleted
        get_response = await client.get(f"/api/articles/{article.slug}/comments")
        assert len(get_response.json()["comments"]) == 0

    @pytest.mark.asyncio
    async def test_delete_comment_not_owner(
        self, client: AsyncClient, test_user: User, auth_headers: dict, auth_headers2: dict, db_session: AsyncSession
    ):
        """Test deleting comment by non-owner fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        add_response = await client.post(
            f"/api/articles/{article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "Test comment"}},
        )
        comment_id = add_response.json()["comment"]["id"]
        
        # Try to delete with different user
        response = await client.delete(
            f"/api/articles/{article.slug}/comments/{comment_id}",
            headers=auth_headers2,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_add_comment_no_auth(self, client: AsyncClient, test_user: User, db_session: AsyncSession):
        """Test adding comment without auth fails."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
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
        
        response = await client.post(
            f"/api/articles/{article.slug}/comments",
            json={"comment": {"body": "Test"}},
        )
        assert response.status_code == 401


class TestTags:
    """Test tags endpoint."""

    @pytest.mark.asyncio
    async def test_get_tags_empty(self, client: AsyncClient):
        """Test getting tags when none exist."""
        response = await client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == []

    @pytest.mark.asyncio
    async def test_get_tags_with_data(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test getting tags after creating articles with tags."""
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        
        # Create articles with tags
        await service.create_article(
            ArticleCreateSchema(
                title="Article 1",
                description="Desc",
                body="Body",
                tagList=["python", "fastapi"],
            ),
            test_user,
        )
        await service.create_article(
            ArticleCreateSchema(
                title="Article 2",
                description="Desc",
                body="Body",
                tagList=["javascript", "react"],
            ),
            test_user,
        )
        await db_session.commit()
        
        response = await client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert set(data["tags"]) == {"python", "fastapi", "javascript", "react"}


class TestFeed:
    """Test feed endpoint GET /api/articles/feed."""

    @pytest.mark.asyncio
    async def test_get_feed_requires_auth(self, client: AsyncClient):
        """Test feed endpoint requires authentication."""
        response = await client.get("/api/articles/feed")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_feed_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test feed returns empty when user follows no one."""
        response = await client.get("/api/articles/feed", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == []
        assert data["articlesCount"] == 0

    @pytest.mark.asyncio
    async def test_get_feed_with_followed_articles(
        self, client: AsyncClient, test_user: User, test_user2: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test feed returns articles from followed users."""
        # User 1 follows user 2
        test_user.following.append(test_user2)
        await db_session.commit()
        
        # User 2 creates article
        service = ArticleService(db_session)
        from app.articles.schemas import ArticleCreateSchema
        await service.create_article(
            ArticleCreateSchema(
                title="Article by followed user",
                description="Desc",
                body="Body",
                tagList=[],
            ),
            test_user2,
        )
        await db_session.commit()
        
        # User 1 gets feed
        response = await client.get("/api/articles/feed", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["author"]["username"] == "testuser2"
