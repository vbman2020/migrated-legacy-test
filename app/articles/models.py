from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, ForeignKey, Index, String, Text, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.models import TimestampedModel

if TYPE_CHECKING:
    from app.auth.models import User


# Association table for article tags (many-to-many)
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# Association table for article favorites (many-to-many)
article_favorites = Table(
    "article_favorites",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Article(TimestampedModel, Base):
    __tablename__ = "articles"
    __table_args__ = (
        Index("idx_articles_author_created", "author_id", "created_at"),
        Index("idx_articles_created_desc", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="articles", foreign_keys=[author_id])
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary=article_tags,
        back_populates="articles",
        lazy="selectin"
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    favorited_by: Mapped[List["User"]] = relationship(
        "User",
        secondary=article_favorites,
        back_populates="favorited_articles"
    )

    def __repr__(self) -> str:
        return f"<Article {self.title}>"


class Comment(TimestampedModel, Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("idx_comments_article_created", "article_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    body: Mapped[str] = mapped_column(Text)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Relationships
    article: Mapped["Article"] = relationship("Article", back_populates="comments")
    author: Mapped["User"] = relationship("User", back_populates="comments", foreign_keys=[author_id])

    def __repr__(self) -> str:
        return f"<Comment {self.id}>"


class Tag(TimestampedModel, Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tag: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Relationships
    articles: Mapped[List["Article"]] = relationship(
        "Article",
        secondary=article_tags,
        back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag {self.tag}>"
