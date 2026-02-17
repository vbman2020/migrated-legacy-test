"""Article, Comment, and Tag SQLAlchemy models."""
from datetime import datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Table, Column, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.auth.models import User
    from app.profiles.models import Profile


# Association table for article tags (many-to-many)
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for article favorites (many-to-many)
article_favorites = Table(
    "article_favorites",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("profile_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Index("idx_article_favorites_article", "article_id"),
    Index("idx_article_favorites_profile", "profile_id"),
)


class Article(Base):
    """Article model representing a blog post."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    author: Mapped["Profile"] = relationship("Profile", back_populates="articles", foreign_keys=[author_id])
    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="article", cascade="all, delete-orphan"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=article_tags, back_populates="articles"
    )
    favorited_by: Mapped[List["Profile"]] = relationship(
        "Profile",
        secondary=article_favorites,
        back_populates="favorites",
    )

    def __repr__(self) -> str:
        return f"<Article {self.title}>"


class Comment(Base):
    """Comment model for article comments."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    article_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    article: Mapped["Article"] = relationship("Article", back_populates="comments")
    author: Mapped["Profile"] = relationship("Profile", back_populates="comments", foreign_keys=[author_id])

    def __repr__(self) -> str:
        return f"<Comment {self.id}>"


class Tag(Base):
    """Tag model for article categorization."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tag: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    articles: Mapped[List["Article"]] = relationship(
        "Article", secondary=article_tags, back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag {self.tag}>"
