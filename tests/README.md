# Test Suite for RealWorld API

Comprehensive pytest test suite for the RealWorld API implementation.

## Setup

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_authentication.py

# Run specific test class
pytest tests/test_articles.py::TestCreateArticle

# Run specific test
pytest tests/test_articles.py::TestCreateArticle::test_create_article_success

# Run with verbose output
pytest tests/ -v

# Run with print statements
pytest tests/ -s
```

## Test Structure

### Core Test Files

- **conftest.py**: Shared fixtures and test configuration
  - Database setup/teardown
  - Test client creation
  - User fixtures (test_user, test_user2)
  - Auth token fixtures
  - Article and comment fixtures

- **test_authentication.py**: User authentication tests
  - User registration
  - Login/logout
  - Get current user
  - Update user profile
  - Password security

- **test_profiles.py**: Profile and follow/unfollow tests
  - Get user profile
  - Follow user
  - Unfollow user
  - Following status tracking

- **test_articles.py**: Article CRUD and interaction tests
  - List articles with filtering
  - Get article feed
  - Create article
  - Update article
  - Delete article
  - Favorite/unfavorite
  - Tag management

- **test_comments.py**: Comment tests
  - Get comments
  - Create comment
  - Delete comment
  - Authorization checks

- **test_integration.py**: End-to-end workflow tests
  - Complete user workflows
  - Multi-user interactions
  - Complex scenarios

- **test_security.py**: Security-focused tests
  - Authentication security
  - XSS prevention
  - SQL injection prevention
  - Authorization checks
  - Input validation

## Test Coverage

### Authentication (test_authentication.py)
- ✅ User registration (success, duplicate email/username, invalid data)
- ✅ User login (success, invalid credentials, case-insensitive)
- ✅ Get current user (with/without auth, invalid token)
- ✅ Update user (email, username, bio, image, password)
- ✅ XSS prevention in user fields

### Profiles (test_profiles.py)
- ✅ Get profile (authenticated/unauthenticated, not found)
- ✅ Follow user (success, already following, self-follow)
- ✅ Unfollow user (success, not following, idempotency)
- ✅ Following status in profile responses

### Articles (test_articles.py)
- ✅ List articles (empty, pagination, filtering by tag/author/favorited)
- ✅ Get feed (requires auth, pagination, followed users only)
- ✅ Create article (success, with tags, validation, slug generation)
- ✅ Get article (success, not found, authenticated/unauthenticated)
- ✅ Update article (full/partial, authorization, not found)
- ✅ Delete article (success, authorization, cascade)
- ✅ Favorite/unfavorite (idempotency, counts)
- ✅ Tags (list, no duplicates)

### Comments (test_comments.py)
- ✅ Get comments (empty, multiple, not found)
- ✅ Create comment (success, validation, XSS prevention)
- ✅ Delete comment (authorization, not found, wrong article)

### Integration (test_integration.py)
- ✅ Complete user registration and login flow
- ✅ User profile update workflow
- ✅ Article CRUD workflow
- ✅ Favorite/unfavorite workflow
- ✅ Comment create/delete workflow
- ✅ Follow and feed workflow
- ✅ Multi-user article interactions

### Security (test_security.py)
- ✅ JWT token requirements
- ✅ Invalid token handling
- ✅ Password never in responses
- ✅ XSS prevention (articles, comments, profiles)
- ✅ SQL injection prevention
- ✅ Authorization checks (cannot modify others' content)
- ✅ Input validation (email, field lengths)

## Fixtures Reference

### Database
- `db_session`: Fresh database session for each test

### HTTP Client
- `client`: Async HTTP client with database override

### Users
- `test_user`: First test user
- `test_user2`: Second test user for multi-user tests
- `auth_token`: JWT token for test_user
- `auth_token2`: JWT token for test_user2
- `auth_headers`: Authorization headers for test_user
- `auth_headers2`: Authorization headers for test_user2

### Content
- `test_article`: Article owned by test_user
- `test_article_with_tags`: Article with tags
- `test_comment`: Comment by test_user on test_article

### Data
- `valid_user_data`: Valid user registration payload
- `valid_login_data`: Valid login payload
- `valid_article_data`: Valid article creation payload
- `valid_comment_data`: Valid comment creation payload

## Writing New Tests

```python
import pytest
from httpx import AsyncClient

class TestYourFeature:
    """Tests for your feature."""

    @pytest.mark.asyncio
    async def test_your_endpoint(self, client: AsyncClient, auth_headers: dict):
        """Test description."""
        response = await client.get("/api/your-endpoint", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "expectedField" in data
```

## Best Practices

1. **Use descriptive test names**: Test names should clearly describe what is being tested
2. **One assertion focus per test**: Each test should focus on one specific behavior
3. **Use fixtures**: Leverage existing fixtures to avoid repetition
4. **Test error cases**: Always test both success and failure scenarios
5. **Test edge cases**: Empty lists, missing fields, invalid data, etc.
6. **Test security**: Always consider security implications (auth, XSS, SQL injection)
7. **Use async/await**: All tests should be async since FastAPI is async
8. **Clean up**: Use fixtures and test database to ensure isolation

## Common Patterns

### Testing protected endpoints
```python
# Without auth (should fail)
response = await client.get("/api/protected")
assert response.status_code == 401

# With auth (should succeed)
response = await client.get("/api/protected", headers=auth_headers)
assert response.status_code == 200
```

### Testing CRUD operations
```python
# Create
create_response = await client.post("/api/resource", headers=auth_headers, json=data)
assert create_response.status_code == 201
resource_id = create_response.json()["id"]

# Read
get_response = await client.get(f"/api/resource/{resource_id}")
assert get_response.status_code == 200

# Update
update_response = await client.put(f"/api/resource/{resource_id}", headers=auth_headers, json=update_data)
assert update_response.status_code == 200

# Delete
delete_response = await client.delete(f"/api/resource/{resource_id}", headers=auth_headers)
assert delete_response.status_code == 204
```

### Testing validation
```python
# Missing required field
response = await client.post("/api/resource", headers=auth_headers, json={})
assert response.status_code == 422

# Invalid format
response = await client.post("/api/resource", headers=auth_headers, json={"email": "invalid"})
assert response.status_code == 422
```
