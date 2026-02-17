"""Pytest configuration and shared fixtures."""
import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import event, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app as main_app
from app.auth.models import User
from app.auth.service import AuthService
from app.profiles.models import Profile


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database session."""
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    
    main_app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=main_app, base_url="http://test") as ac:
        yield ac
    
    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = await AuthService.create_user(
        db=db_session,
        username="testuser",
        email="test@example.com",
        password="password123"
    )
    
    # Create profile for user
    profile = Profile(user_id=user.id, bio="Test bio", image="")
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """Create a second test user."""
    user = await AuthService.create_user(
        db=db_session,
        username="testuser2",
        email="test2@example.com",
        password="password123"
    )
    
    # Create profile for user
    profile = Profile(user_id=user.id, bio="Test bio 2", image="")
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def auth_token(test_user: User) -> str:
    """Get authentication token for test user."""
    return AuthService.create_access_token(test_user.id)


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    """Get authentication headers for test user."""
    return {"Authorization": f"Token {auth_token}"}


@pytest_asyncio.fixture
async def auth_token2(test_user2: User) -> str:
    """Get authentication token for second test user."""
    return AuthService.create_access_token(test_user2.id)


@pytest_asyncio.fixture
async def auth_headers2(auth_token2: str) -> dict:
    """Get authentication headers for second test user."""
    return {"Authorization": f"Token {auth_token2}"}
