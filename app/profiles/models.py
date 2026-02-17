from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, List

from app.database import Base
from app.core.models import TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.articles.models import Article


# Association table for follows (self-referential many-to-many)
follows_table = Table(
    "follows",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("followee_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for favorites (many-to-many with articles)
favorites_table = Table(
    "favorites",
    Base.metadata,
    Column("profile_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
)


class Profile(Base, TimestampMixin):
    """Profile model representing user profiles with follow and favorite relationships."""
    
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image: Mapped[str] = mapped_column(String, default="", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")
    
    # Self-referential many-to-many for follows
    # follows: profiles that this profile is following
    follows: Mapped[List["Profile"]] = relationship(
        "Profile",
        secondary=follows_table,
        primaryjoin=(id == follows_table.c.follower_id),
        secondaryjoin=(id == follows_table.c.followee_id),
        foreign_keys=[follows_table.c.follower_id, follows_table.c.followee_id],
        backref="followed_by",
        lazy="selectin",
    )
    
    # Many-to-many with articles for favorites
    favorites: Mapped[List["Article"]] = relationship(
        "Article",
        secondary=favorites_table,
        back_populates="favorited_by",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, user_id={self.user_id})>"
