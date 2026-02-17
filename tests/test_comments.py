"""Tests for comment endpoints."""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.articles.models import Article, Comment


@pytest_asyncio.fixture
async def test_article(db_session: AsyncSession, test_user: User) -> Article:
    """Create a test article."""
    from app.articles.service import create_article
    from app.articles.schemas import ArticleCreate
    
    article_data = ArticleCreate(
        title="Test Article",
        description="Test description",
        body="Test body content",
        tag_list=["test"]
    )
    
    article = await create_article(db_session, article_data, test_user)
    return article


@pytest_asyncio.fixture
async def test_comment(db_session: AsyncSession, test_article: Article, test_user: User) -> Comment:
    """Create a test comment."""
    comment = Comment(
        body="Test comment",
        article_id=test_article.id,
        author_id=test_user.id
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


class TestGetComments:
    """Tests for GET /api/articles/{slug}/comments."""
    
    @pytest.mark.asyncio
    async def test_get_comments_empty(self, client: AsyncClient, test_article: Article):
        """Test getting comments when none exist."""
        response = await client.get(f"/api/articles/{test_article.slug}/comments")
        
        assert response.status_code == 200
        data = response.json()
        assert data["comments"] == []
    
    @pytest.mark.asyncio
    async def test_get_comments_with_comments(self, client: AsyncClient, test_article: Article, test_comment: Comment):
        """Test getting comments returns created comments."""
        response = await client.get(f"/api/articles/{test_article.slug}/comments")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 1
        assert data["comments"][0]["body"] == "Test comment"
    
    @pytest.mark.asyncio
    async def test_get_comments_nonexistent_article(self, client: AsyncClient):
        """Test getting comments for non-existent article returns 404."""
        response = await client.get("/api/articles/nonexistent/comments")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_comments_includes_author(self, client: AsyncClient, test_article: Article, test_comment: Comment):
        """Test comment response includes author information."""
        response = await client.get(f"/api/articles/{test_article.slug}/comments")
        
        assert response.status_code == 200
        data = response.json()
        assert "author" in data["comments"][0]
        assert data["comments"][0]["author"]["username"] == "testuser"


class TestAddComment:
    """Tests for POST /api/articles/{slug}/comments."""
    
    @pytest.mark.asyncio
    async def test_add_comment_success(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test successfully adding a comment."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={
                "comment": {
                    "body": "Great article!"
                }
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "comment" in data
        assert data["comment"]["body"] == "Great article!"
        assert data["comment"]["author"]["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_add_comment_no_auth(self, client: AsyncClient, test_article: Article):
        """Test adding comment without authentication fails."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            json={
                "comment": {
                    "body": "Great article!"
                }
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_add_comment_empty_body(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test adding comment with empty body fails."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={
                "comment": {
                    "body": "   "
                }
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_add_comment_nonexistent_article(self, client: AsyncClient, auth_headers: dict):
        """Test adding comment to non-existent article returns 404."""
        response = await client.post(
            "/api/articles/nonexistent/comments",
            headers=auth_headers,
            json={
                "comment": {
                    "body": "Great article!"
                }
            }
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_add_comment_missing_comment_key(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test adding comment without 'comment' wrapper key fails."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={
                "body": "Great article!"
            }
        )
        
        assert response.status_code == 422


class TestDeleteComment:
    """Tests for DELETE /api/articles/{slug}/comments/{id}."""
    
    @pytest.mark.asyncio
    async def test_delete_comment_success(self, client: AsyncClient, test_article: Article, test_comment: Comment, auth_headers: dict):
        """Test successfully deleting a comment."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{test_comment.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify comment is deleted
        get_response = await client.get(f"/api/articles/{test_article.slug}/comments")
        assert len(get_response.json()["comments"]) == 0
    
    @pytest.mark.asyncio
    async def test_delete_comment_not_author(self, client: AsyncClient, test_article: Article, test_comment: Comment, auth_headers2: dict):
        """Test deleting comment by non-author fails."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{test_comment.id}",
            headers=auth_headers2
        )
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_delete_comment_no_auth(self, client: AsyncClient, test_article: Article, test_comment: Comment):
        """Test deleting comment without authentication fails."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{test_comment.id}"
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_delete_comment_nonexistent(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test deleting non-existent comment returns 404."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/99999",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_comment_wrong_article(self, client: AsyncClient, test_article: Article, test_comment: Comment, auth_headers: dict, db_session: AsyncSession, test_user: User):
        """Test deleting comment with wrong article slug returns 404."""
        # Create another article
        from app.articles.service import create_article
        from app.articles.schemas import ArticleCreate
        
        article_data = ArticleCreate(
            title="Another Article",
            description="Description",
            body="Body"
        )
        another_article = await create_article(db_session, article_data, test_user)
        
        response = await client.delete(
            f"/api/articles/{another_article.slug}/comments/{test_comment.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
