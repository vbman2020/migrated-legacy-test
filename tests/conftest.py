"""Pytest configuration and shared fixtures."""
import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.auth.models import User
from app.profiles.models import Profile
from app.articles.models import Article, Tag, Comment
from app.auth.service import create_access_token, hash_password

# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Drop tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("TestPass123!"),
        is_active=True,
    )
    db_session.add(user)
    
    # Create associated profile
    profile = Profile(
        user=user,
        bio="Test bio",
        image="https://example.com/image.jpg"
    )
    db_session.add(profile)
    
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """Create a second test user."""
    user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash=hash_password("TestPass123!"),
        is_active=True,
    )
    db_session.add(user)
    
    profile = Profile(
        user=user,
        bio="Test bio 2",
        image="https://example.com/image2.jpg"
    )
    db_session.add(profile)
    
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Create authentication headers for test user."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Token {token}"}


@pytest.fixture
def auth_headers2(test_user2: User) -> dict[str, str]:
    """Create authentication headers for second test user."""
    token = create_access_token(test_user2.id)
    return {"Authorization": f"Token {token}"}


@pytest_asyncio.fixture
async def test_article(db_session: AsyncSession, test_user: User) -> Article:
    """Create a test article."""
    article = Article(
        slug="test-article-abc123",
        title="Test Article",
        description="Test description",
        body="Test body content",
        author_id=test_user.profile.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def test_article_with_tags(db_session: AsyncSession, test_user: User) -> Article:
    """Create a test article with tags."""
    article = Article(
        slug="test-article-tags-xyz789",
        title="Test Article with Tags",
        description="Test description",
        body="Test body content",
        author_id=test_user.profile.id,
    )
    
    # Add tags
    tag1 = Tag(tag="testing")
    tag2 = Tag(tag="python")
    db_session.add(tag1)
    db_session.add(tag2)
    
    article.tags = [tag1, tag2]
    db_session.add(article)
    
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def test_comment(db_session: AsyncSession, test_article: Article, test_user2: User) -> Comment:
    """Create a test comment."""
    comment = Comment(
        body="Test comment",
        article_id=test_article.id,
        author_id=test_user2.profile.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


@pytest_asyncio.fixture
async def test_tags(db_session: AsyncSession) -> list[Tag]:
    """Create test tags."""
    tags = [
        Tag(tag="python"),
        Tag(tag="fastapi"),
        Tag(tag="testing"),
    ]
    for tag in tags:
        db_session.add(tag)
    await db_session.commit()
    return tags
