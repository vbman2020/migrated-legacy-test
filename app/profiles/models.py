from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.database import Base
from app.core.models import TimestampedModel

if TYPE_CHECKING:
    from app.auth.models import User
    from app.articles.models import Article


# Association table for follow relationships (self-referential many-to-many)
follows = Table(
    "follows",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("followee_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
)


# Association table for favorites (many-to-many between profiles and articles)
favorites = Table(
    "favorites",
    Base.metadata,
    Column("profile_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
)


class Profile(TimestampedModel):
    """Profile model representing user profiles with bio, image, and relationships."""
    
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    image: Mapped[str | None] = mapped_column(String(500), nullable=True, default="")

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile", lazy="joined")
    
    # Self-referential many-to-many for follow relationships
    # followers = users who follow this profile
    # following = users this profile follows
    following: Mapped[list["Profile"]] = relationship(
        "Profile",
        secondary=follows,
        primaryjoin=(id == follows.c.follower_id),
        secondaryjoin=(id == follows.c.followee_id),
        back_populates="followers",
        lazy="selectin",
    )
    
    followers: Mapped[list["Profile"]] = relationship(
        "Profile",
        secondary=follows,
        primaryjoin=(id == follows.c.followee_id),
        secondaryjoin=(id == follows.c.follower_id),
        back_populates="following",
        lazy="selectin",
    )
    
    # Many-to-many relationship with articles (favorites)
    favorited_articles: Mapped[list["Article"]] = relationship(
        "Article",
        secondary=favorites,
        back_populates="favorited_by",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, user_id={self.user_id})>"
