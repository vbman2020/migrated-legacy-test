"""Shared pytest fixtures for all tests.

Provides database session, test client, and authentication helpers.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.auth.models import User
from app.auth.service import AuthService

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

# Create async session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test.
    
    Creates all tables before the test and drops them after.
    """
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    
    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
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
        password="TestPass123!",
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
        password="TestPass123!",
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(test_user: User, db_session: AsyncSession) -> str:
    """Get authentication token for test user."""
    auth_service = AuthService(db_session)
    token = auth_service.create_access_token(user_id=test_user.id)
    return token


@pytest_asyncio.fixture
async def auth_token2(test_user2: User, db_session: AsyncSession) -> str:
    """Get authentication token for second test user."""
    auth_service = AuthService(db_session)
    token = auth_service.create_access_token(user_id=test_user2.id)
    return token


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    """Get authorization headers for test user."""
    return {"Authorization": f"Token {auth_token}"}


@pytest_asyncio.fixture
async def auth_headers2(auth_token2: str) -> dict:
    """Get authorization headers for second test user."""
    return {"Authorization": f"Token {auth_token2}"}


# Sample data fixtures
@pytest.fixture
def sample_user_data() -> dict:
    """Sample user registration data."""
    return {
        "user": {
            "email": "jake@jake.jake",
            "username": "jakejake",
            "password": "JakePass123!",
        }
    }


@pytest.fixture
def sample_article_data() -> dict:
    """Sample article creation data."""
    return {
        "article": {
            "title": "How to train your dragon",
            "description": "Ever wonder how?",
            "body": "You have to believe",
            "tagList": ["dragons", "training"],
        }
    }


@pytest.fixture
def sample_comment_data() -> dict:
    """Sample comment creation data."""
    return {
        "comment": {
            "body": "This is a great article!",
        }
    }


@pytest.fixture
def sample_profile_update() -> dict:
    """Sample profile update data."""
    return {
        "user": {
            "email": "newemail@example.com",
            "bio": "I like to code",
            "image": "https://example.com/avatar.jpg",
        }
    }
