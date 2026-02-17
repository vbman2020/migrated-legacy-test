"""Tests for comment endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.articles.models import Article, Comment


class TestGetComments:
    """Tests for GET /api/articles/{slug}/comments endpoint."""

    @pytest.mark.asyncio
    async def test_get_comments_empty(self, client: AsyncClient, test_article: Article):
        """Test getting comments when none exist."""
        response = await client.get(f"/api/articles/{test_article.slug}/comments")
        
        assert response.status_code == 200
        data = response.json()
        assert "comments" in data
        assert data["comments"] == []

    @pytest.mark.asyncio
    async def test_get_comments_with_comments(self, client: AsyncClient, test_article: Article, test_comment: Comment):
        """Test getting comments when they exist."""
        response = await client.get(f"/api/articles/{test_article.slug}/comments")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 1
        assert data["comments"][0]["body"] == test_comment.body
        assert data["comments"][0]["id"] == test_comment.id

    @pytest.mark.asyncio
    async def test_get_comments_article_not_found(self, client: AsyncClient):
        """Test getting comments for non-existent article."""
        response = await client.get("/api/articles/nonexistent-slug/comments")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_comments_multiple(self, client: AsyncClient, test_article: Article, test_user: User, test_user2: User, db_session: AsyncSession):
        """Test getting multiple comments."""
        # Create multiple comments
        for i in range(3):
            comment = Comment(
                body=f"Comment {i}",
                article_id=test_article.id,
                author_id=test_user.id if i % 2 == 0 else test_user2.id,
            )
            db_session.add(comment)
        await db_session.commit()
        
        response = await client.get(f"/api/articles/{test_article.slug}/comments")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 3

    @pytest.mark.asyncio
    async def test_get_comments_with_auth(self, client: AsyncClient, test_article: Article, test_comment: Comment, auth_headers: dict):
        """Test getting comments while authenticated."""
        response = await client.get(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 1
        # Author should include following status
        assert "following" in data["comments"][0]["author"]


class TestCreateComment:
    """Tests for POST /api/articles/{slug}/comments endpoint."""

    @pytest.mark.asyncio
    async def test_create_comment_success(self, client: AsyncClient, test_article: Article, auth_headers: dict, valid_comment_data: dict):
        """Test successfully creating a comment."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json=valid_comment_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "comment" in data
        assert data["comment"]["body"] == valid_comment_data["comment"]["body"]
        assert "id" in data["comment"]
        assert "createdAt" in data["comment"]
        assert "author" in data["comment"]

    @pytest.mark.asyncio
    async def test_create_comment_no_auth(self, client: AsyncClient, test_article: Article, valid_comment_data: dict):
        """Test creating comment without authentication."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            json=valid_comment_data
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_comment_article_not_found(self, client: AsyncClient, auth_headers: dict, valid_comment_data: dict):
        """Test creating comment for non-existent article."""
        response = await client.post(
            "/api/articles/nonexistent-slug/comments",
            headers=auth_headers,
            json=valid_comment_data
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_comment_missing_body(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test creating comment without body."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={"comment": {}}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comment_empty_body(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test creating comment with empty body."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": ""}}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comment_body_too_long(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test creating comment with body exceeding max length."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "a" * 50001}}  # Exceeds MAX_COMMENT_BODY_LENGTH
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comment_xss_prevention(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test XSS prevention in comment body."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={"comment": {"body": "<script>alert('xss')</script>"}}
        )
        
        assert response.status_code in [201, 422]
        if response.status_code == 201:
            data = response.json()
            # Content should be sanitized
            assert "<script>" not in data["comment"]["body"]

    @pytest.mark.asyncio
    async def test_create_multiple_comments(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test creating multiple comments on same article."""
        for i in range(3):
            response = await client.post(
                f"/api/articles/{test_article.slug}/comments",
                headers=auth_headers,
                json={"comment": {"body": f"Comment {i}"}}
            )
            assert response.status_code == 201
        
        # Verify all comments exist
        get_response = await client.get(f"/api/articles/{test_article.slug}/comments")
        data = get_response.json()
        assert len(data["comments"]) == 3


class TestDeleteComment:
    """Tests for DELETE /api/articles/{slug}/comments/{id} endpoint."""

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
        data = get_response.json()
        assert len(data["comments"]) == 0

    @pytest.mark.asyncio
    async def test_delete_comment_not_owner(self, client: AsyncClient, test_article: Article, test_comment: Comment, auth_headers2: dict):
        """Test deleting comment by non-owner."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{test_comment.id}",
            headers=auth_headers2
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment_no_auth(self, client: AsyncClient, test_article: Article, test_comment: Comment):
        """Test deleting comment without authentication."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{test_comment.id}"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_comment_not_found(self, client: AsyncClient, test_article: Article, auth_headers: dict):
        """Test deleting non-existent comment."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/99999",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_comment_wrong_article(self, client: AsyncClient, test_article: Article, test_comment: Comment, auth_headers: dict, db_session: AsyncSession, test_user: User):
        """Test deleting comment with wrong article slug."""
        # Create another article
        article2 = Article(
            slug="another-article",
            title="Another Article",
            description="Description",
            body="Body",
            author_id=test_user.id,
        )
        db_session.add(article2)
        await db_session.commit()
        
        # Try to delete comment using wrong article slug
        response = await client.delete(
            f"/api/articles/{article2.slug}/comments/{test_comment.id}",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_comment_article_owner_not_comment_owner(self, client: AsyncClient, test_article: Article, test_user2: User, auth_headers: dict, db_session: AsyncSession):
        """Test that article owner cannot delete other users' comments."""
        # Create comment by another user
        comment = Comment(
            body="Comment by user2",
            article_id=test_article.id,
            author_id=test_user2.id,
        )
        db_session.add(comment)
        await db_session.commit()
        await db_session.refresh(comment)
        
        # Try to delete as article owner (not comment owner)
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{comment.id}",
            headers=auth_headers
        )
        
        # Should fail - only comment owner can delete
        assert response.status_code == 403
