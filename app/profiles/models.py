"""Profile models and association tables.

This module defines the association tables for follower/following relationships
and favorites. In this architecture, profile data (bio, image) is stored directly
on the User model rather than in a separate Profile model.
"""

from sqlalchemy import Table, Column, Integer, ForeignKey

from app.database import Base

# Association table for follower/following relationships
# A user (follower_id) follows another user (followed_id)
follower_association = Table(
    'followers_association',
    Base.metadata,
    Column('follower_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('followed_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
)

# Association table for user favorites
# A user favorites an article
favorite_association = Table(
    'favorite_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('article_id', Integer, ForeignKey('articles.id', ondelete='CASCADE'), primary_key=True)
)
