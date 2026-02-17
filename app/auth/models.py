"""SQLAlchemy User model with authentication support."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.profiles.models import Profile
    from app.articles.models import Article, Comment


class User(Base):
    """User model for authentication and authorization.
    
    Attributes:
        id: Primary key
        username: Unique username for the user
        email: Unique email address used for login
        password_hash: Hashed password using bcrypt (60 characters)
        is_active: Whether the user account is active
        is_staff: Whether the user has staff privileges
        is_superuser: Whether the user has superuser privileges
        created_at: Timestamp of user creation
        updated_at: Timestamp of last update
        profile: One-to-one relationship with Profile model
        articles: One-to-many relationship with Article model
        comments: One-to-many relationship with Comment model
        favorited_articles: Many-to-many relationship with favorited articles
        following: Many-to-many relationship with users being followed
        followers: Many-to-many relationship with follower users
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationship with Profile (one-to-one)
    profile: Mapped["Profile"] = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Relationship with Articles (one-to-many)
    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="author",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    # Relationship with Comments (one-to-many)
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="author",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    # Relationship with favorited articles (many-to-many)
    # Defined in articles.models.py as article_favorites association table
    favorited_articles: Mapped[List["Article"]] = relationship(
        "Article",
        secondary="article_favorites",
        back_populates="favorited_by",
        lazy="select"
    )
    
    # Relationship with following/followers (many-to-many)
    # Defined in profiles.models.py as follower_association table
    following: Mapped[List["User"]] = relationship(
        "User",
        secondary="follower_association",
        primaryjoin="User.id==follower_association.c.follower_id",
        secondaryjoin="User.id==follower_association.c.following_id",
        back_populates="followers",
        lazy="select"
    )
    
    followers: Mapped[List["User"]] = relationship(
        "User",
        secondary="follower_association",
        primaryjoin="User.id==follower_association.c.following_id",
        secondaryjoin="User.id==follower_association.c.follower_id",
        back_populates="following",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        """String representation of the User."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
