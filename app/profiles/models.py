from sqlalchemy import Column, ForeignKey, Integer, Table

from app.database import Base

# Many-to-many association table for user follows
# A user can follow many users and be followed by many users
user_follows = Table(
    "user_follows",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("followee_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)
