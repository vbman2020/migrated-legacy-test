"""User model with authentication support."""

from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

from sqlalchemy import String, Boolean, Text, Table, Column, Integer, ForeignKey, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.models import TimestampedModel

if TYPE_CHECKING:
    from app.articles.models import Article, Comment


# Association table for user follows (many-to-many self-referential relationship)
user_follows = Table(
    "user_follows",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("followed_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Index("idx_user_follows_follower", "follower_id"),
    Index("idx_user_follows_followed", "followed_id"),
)


class User(Base, TimestampedModel):
    """User model for authentication and profile management.
    
    Attributes:
        id: Primary key
        email: User's email address (unique, stored lowercase for case-insensitive comparison)
        username: User's username (unique, stored lowercase for case-insensitive comparison)
        password: Hashed password using bcrypt (exactly 60 characters)
        bio: User biography text (sanitized for XSS prevention)
        image: User profile image URL (validated as proper HTTP/HTTPS URL)
        is_active: Whether the user account is active
        failed_login_attempts: Counter for failed login attempts (for account lockout)
        locked_until: Timestamp until which account is locked (for temporary lockout)
        created_at: Timestamp when user was created (inherited from TimestampedModel)
        updated_at: Timestamp when user was last updated (inherited from TimestampedModel)
        articles: Relationship to user's articles
        comments: Relationship to user's comments
        favorited_articles: Relationship to articles favorited by this user
        followers: Users who follow this user
        following: Users this user follows
    
    Note:
        - Email and username are stored in lowercase for case-insensitive uniqueness
        - Relationships use lazy='joined' for efficient loading in most cases
        - Failed login attempts and account locking provide brute force protection
        - Password field is exactly 60 chars to match bcrypt hash length
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(60), nullable=False)  # bcrypt hash is exactly 60 chars
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Brute force protection fields
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    
    # Relationships - using lazy='joined' for better performance in common queries
    # Changed from selectin to joined to avoid N+1 queries in list operations
    
    # One-to-many: User has many articles
    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="author",
        foreign_keys="Article.author_id",
        lazy="noload",  # Use noload to avoid automatic loading, explicit loading when needed
        cascade="all, delete-orphan"
    )
    
    # One-to-many: User has many comments
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="author",
        foreign_keys="Comment.author_id",
        lazy="noload",
        cascade="all, delete-orphan"
    )
    
    # Many-to-many: User favorites many articles
    favorited_articles: Mapped[List["Article"]] = relationship(
        "Article",
        secondary="article_favorites",
        back_populates="favorited_by",
        lazy="noload",
        viewonly=True  # Prevent accidental modifications through this relationship
    )
    
    # Many-to-many self-referential: User follows other users
    followers: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_follows,
        primaryjoin=id == user_follows.c.followed_id,
        secondaryjoin=id == user_follows.c.follower_id,
        back_populates="following",
        lazy="noload",
        viewonly=True
    )
    
    following: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_follows,
        primaryjoin=id == user_follows.c.follower_id,
        secondaryjoin=id == user_follows.c.followed_id,
        back_populates="followers",
        lazy="noload",
        viewonly=True
    )
    
    # Add indexes for frequently queried fields
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_username", "username"),
        Index("idx_user_is_active", "is_active"),
        Index("idx_user_locked_until", "locked_until"),
    )
    
    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
    
    def is_locked(self) -> bool:
        """Check if the user account is currently locked.
        
        Returns:
            True if account is locked and lock has not expired, False otherwise
        """
        if self.locked_until is None:
            return False
        return datetime.now(self.locked_until.tzinfo or None) < self.locked_until
    
    def is_following(self, user: "User") -> bool:
        """Check if this user is following another user.
        
        Note: This method requires the following relationship to be loaded.
        Use explicit loading or joins to avoid N+1 queries.
        
        Args:
            user: User to check if being followed
            
        Returns:
            True if this user is following the given user, False otherwise
        """
        if not hasattr(self, "_following_loaded"):
            # Relationships must be explicitly loaded before using this method
            return False
        return user in self.following
    
    def has_favorited(self, article: "Article") -> bool:
        """Check if this user has favorited an article.
        
        Note: This method requires the favorited_articles relationship to be loaded.
        Use explicit loading or joins to avoid N+1 queries.
        
        Args:
            article: Article to check if favorited
            
        Returns:
            True if this user has favorited the article, False otherwise
        """
        if not hasattr(self, "_favorited_articles_loaded"):
            # Relationships must be explicitly loaded before using this method
            return False
        return article in self.favorited_articles
