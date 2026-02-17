"""Security-focused tests."""

import pytest
from httpx import AsyncClient


class TestAuthenticationSecurity:
    """Tests for authentication security."""

    @pytest.mark.asyncio
    async def test_jwt_token_required_endpoints(self, client: AsyncClient):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            ("GET", "/api/user"),
            ("PUT", "/api/user"),
            ("GET", "/api/articles/feed"),
            ("POST", "/api/articles"),
        ]
        
        for method, endpoint in protected_endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "PUT":
                response = await client.put(endpoint, json={})
            elif method == "POST":
                response = await client.post(endpoint, json={})
            
            assert response.status_code == 401, f"Endpoint {method} {endpoint} should require auth"

    @pytest.mark.asyncio
    async def test_invalid_token_format(self, client: AsyncClient):
        """Test with malformed tokens."""
        invalid_tokens = [
            "Bearer invalid",  # Wrong scheme
            "Token",  # Missing token
            "invalid",  # Missing scheme
            "Token " + "a" * 1000,  # Extremely long token
        ]
        
        for token in invalid_tokens:
            response = await client.get(
                "/api/user",
                headers={"Authorization": token}
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_password_not_in_response(self, client: AsyncClient, test_user, auth_headers: dict):
        """Test that password is never returned in responses."""
        # Get current user
        response = await client.get("/api/user", headers=auth_headers)
        data = response.json()
        assert "password" not in data["user"]
        
        # Update user
        response = await client.put(
            "/api/user",
            headers=auth_headers,
            json={"user": {"bio": "Test bio"}}
        )
        data = response.json()
        assert "password" not in data["user"]


class TestXSSPrevention:
    """Tests for XSS prevention."""

    @pytest.mark.asyncio
    async def test_xss_in_article_fields(self, client: AsyncClient, auth_headers: dict):
        """Test XSS prevention in article fields."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>",
            "<svg onload=alert('xss')>",
        ]
        
        for payload in xss_payloads:
            response = await client.post(
                "/api/articles",
                headers=auth_headers,
                json={
                    "article": {
                        "title": payload,
                        "description": payload,
                        "body": payload,
                        "tagList": []
                    }
                }
            )
            
            # Either rejected or sanitized
            if response.status_code == 201:
                data = response.json()
                # Verify dangerous HTML is not present
                assert "<script>" not in str(data)
                assert "javascript:" not in str(data)
                assert "onerror=" not in str(data)

    @pytest.mark.asyncio
    async def test_xss_in_comment(self, client: AsyncClient, test_article, auth_headers: dict):
        """Test XSS prevention in comments."""
        response = await client.post(
            f"/api/articles/{test_article.slug}/comments",
            headers=auth_headers,
            json={
                "comment": {
                    "body": "<script>alert('xss')</script>"
                }
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            assert "<script>" not in data["comment"]["body"]


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_filters(self, client: AsyncClient):
        """Test SQL injection attempts in query parameters."""
        sql_payloads = [
            "' OR '1'='1",
            "1; DROP TABLE users--",
            "' UNION SELECT * FROM users--",
        ]
        
        for payload in sql_payloads:
            # Test in various query parameters
            response = await client.get(f"/api/articles?author={payload}")
            assert response.status_code in [200, 422]  # Should handle gracefully
            
            response = await client.get(f"/api/articles?tag={payload}")
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_sql_injection_in_slug(self, client: AsyncClient):
        """Test SQL injection in slug parameter."""
        response = await client.get("/api/articles/' OR '1'='1")
        assert response.status_code in [404, 422]  # Should not cause error


class TestRateLimiting:
    """Tests for rate limiting (if implemented)."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Rate limiting not implemented yet")
    async def test_login_rate_limiting(self, client: AsyncClient):
        """Test that login endpoint has rate limiting."""
        # Attempt many failed logins
        for _ in range(20):
            await client.post(
                "/api/users/login",
                json={
                    "user": {
                        "email": "test@example.com",
                        "password": "wrong"
                    }
                }
            )
        
        # Should eventually get rate limited
        response = await client.post(
            "/api/users/login",
            json={
                "user": {
                    "email": "test@example.com",
                    "password": "wrong"
                }
            }
        )
        assert response.status_code == 429


class TestAuthorizationSecurity:
    """Tests for proper authorization checks."""

    @pytest.mark.asyncio
    async def test_cannot_update_other_user_article(self, client: AsyncClient, test_article, auth_headers2: dict):
        """Test that users cannot modify other users' articles."""
        response = await client.put(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers2,
            json={
                "article": {"title": "Hacked title"}
            }
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_delete_other_user_article(self, client: AsyncClient, test_article, auth_headers2: dict):
        """Test that users cannot delete other users' articles."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}",
            headers=auth_headers2
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_delete_other_user_comment(self, client: AsyncClient, test_article, test_comment, auth_headers2: dict):
        """Test that users cannot delete other users' comments."""
        response = await client.delete(
            f"/api/articles/{test_article.slug}/comments/{test_comment.id}",
            headers=auth_headers2
        )
        assert response.status_code == 403


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_email_validation(self, client: AsyncClient):
        """Test email format validation."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",
            "",
        ]
        
        for email in invalid_emails:
            response = await client.post(
                "/api/users",
                json={
                    "user": {
                        "email": email,
                        "username": "testuser",
                        "password": "Password123!@#"
                    }
                }
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_field_length_validation(self, client: AsyncClient, auth_headers: dict):
        """Test maximum field length validation."""
        # Test extremely long title
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "a" * 300,  # Exceeds MAX_TITLE_LENGTH
                    "description": "Description",
                    "body": "Body"
                }
            }
        )
        assert response.status_code == 422
        
        # Test extremely long body
        response = await client.post(
            "/api/articles",
            headers=auth_headers,
            json={
                "article": {
                    "title": "Title",
                    "description": "Description",
                    "body": "a" * 500001  # Exceeds MAX_ARTICLE_BODY_LENGTH
                }
            }
        )
        assert response.status_code == 422
