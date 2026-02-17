"""Shared pytest fixtures and configuration."""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.auth.models import User
from app.articles.models import Article, Tag, Comment
from app.auth.service import AuthService

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

# Create async session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    
    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    auth_service = AuthService(db_session)
    user = await auth_service.create_user(
        email="test@example.com",
        username="testuser",
        password="Test123!@#",
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """Create a second test user."""
    auth_service = AuthService(db_session)
    user = await auth_service.create_user(
        email="test2@example.com",
        username="testuser2",
        password="Test123!@#",
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(test_user: User, db_session: AsyncSession) -> str:
    """Create JWT token for test user."""
    auth_service = AuthService(db_session)
    token = auth_service.create_access_token(user_id=test_user.id)
    return token


@pytest_asyncio.fixture
async def auth_token2(test_user2: User, db_session: AsyncSession) -> str:
    """Create JWT token for second test user."""
    auth_service = AuthService(db_session)
    token = auth_service.create_access_token(user_id=test_user2.id)
    return token


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    """Create authorization headers with token."""
    return {"Authorization": f"Token {auth_token}"}


@pytest_asyncio.fixture
async def auth_headers2(auth_token2: str) -> dict:
    """Create authorization headers for second user."""
    return {"Authorization": f"Token {auth_token2}"}


@pytest_asyncio.fixture
async def test_article(db_session: AsyncSession, test_user: User) -> Article:
    """Create a test article."""
    article = Article(
        slug="test-article-abc123",
        title="Test Article",
        description="Test description",
        body="Test body content",
        author_id=test_user.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def test_article_with_tags(db_session: AsyncSession, test_user: User) -> Article:
    """Create a test article with tags."""
    # Create tags
    tag1 = Tag(tag="python", slug="python")
    tag2 = Tag(tag="testing", slug="testing")
    db_session.add(tag1)
    db_session.add(tag2)
    await db_session.flush()
    
    # Create article with tags
    article = Article(
        slug="test-article-with-tags-xyz789",
        title="Test Article With Tags",
        description="Test description",
        body="Test body content",
        author_id=test_user.id,
        tags=[tag1, tag2],
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def test_comment(db_session: AsyncSession, test_article: Article, test_user: User) -> Comment:
    """Create a test comment."""
    comment = Comment(
        body="Test comment body",
        article_id=test_article.id,
        author_id=test_user.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


@pytest.fixture
def valid_user_data() -> dict:
    """Valid user registration data."""
    return {
        "user": {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "Password123!@#",
        }
    }


@pytest.fixture
def valid_login_data() -> dict:
    """Valid user login data."""
    return {
        "user": {
            "email": "test@example.com",
            "password": "Test123!@#",
        }
    }


@pytest.fixture
def valid_article_data() -> dict:
    """Valid article creation data."""
    return {
        "article": {
            "title": "How to train your dragon",
            "description": "Ever wonder how?",
            "body": "You have to believe in yourself",
            "tagList": ["dragons", "training"],
        }
    }


@pytest.fixture
def valid_comment_data() -> dict:
    """Valid comment creation data."""
    return {
        "comment": {
            "body": "This is a great article!",
        }
    }
