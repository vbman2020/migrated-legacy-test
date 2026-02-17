"""Authentication models for the FastAPI application.

This module contains the User ORM model definition.
Business logic (password hashing, JWT generation) is handled in the service layer.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, Integer, Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.profiles.models import Profile
    from app.articles.models import Article, Comment


# Association table for user followers (many-to-many self-referential)
user_followers = Table(
    'user_followers',
    Base.metadata,
    Column('follower_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('followed_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    """User model for authentication and profile management.
    
    This model stores user credentials and metadata.
    Business logic (password hashing, JWT) is handled in AuthService.
    The password field stores bcrypt hashed passwords (60 characters).
    """
    
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Password field stores bcrypt hash (always 60 chars), using 255 for safety
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to profile (one-to-one)
    profile: Mapped["Profile"] = relationship(
        "Profile", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Relationship to articles authored by this user
    articles: Mapped[list["Article"]] = relationship(
        "Article", 
        back_populates="author", 
        cascade="all, delete-orphan",
        foreign_keys="Article.author_id",
        lazy="select"
    )
    
    # Relationship to comments authored by this user
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", 
        back_populates="author", 
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    # Relationship to favorited articles
    favorited_articles: Mapped[list["Article"]] = relationship(
        "Article",
        secondary="article_favorites",
        back_populates="favorited_by",
        lazy="select"
    )
    
    # Self-referential many-to-many relationship for following users
    # Users that this user follows
    following: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_followers,
        primaryjoin=lambda: User.id == user_followers.c.follower_id,
        secondaryjoin=lambda: User.id == user_followers.c.followed_id,
        back_populates="followers",
        lazy="select"
    )
    
    # Users that follow this user
    followers: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_followers,
        primaryjoin=lambda: User.id == user_followers.c.followed_id,
        secondaryjoin=lambda: User.id == user_followers.c.follower_id,
        back_populates="following",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
