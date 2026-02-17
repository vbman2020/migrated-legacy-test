"""Profile business logic and database operations.

Provides services for:
- Retrieving user profiles
- Managing follow relationships
- Checking follow status
"""

from typing import Optional
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.profiles.models import follower_association
from app.profiles.schemas import ProfileResponse


class ProfileService:
    """Service class for profile-related operations.
    
    Handles all business logic related to user profiles and follow relationships.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize the profile service.
        
        Args:
            db: Async database session
        """
        self.db = db
    
    async def get_profile_by_username(
        self,
        username: str,
        current_user: Optional[User] = None
    ) -> Optional[ProfileResponse]:
        """Retrieve a user profile by username.
        
        Args:
            username: The username to look up
            current_user: The currently authenticated user (optional)
        
        Returns:
            ProfileResponse if found, None otherwise
        """
        # Query for the user by username
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Check if current user is following this profile
        following = False
        if current_user:
            following = await self.is_following(current_user.id, user.id)
        
        return ProfileResponse(
            username=user.username,
            bio=user.bio or "",
            image=user.image or "https://static.productionready.io/images/smiley-cyrus.jpg",
            following=following
        )
    
    async def follow_user(
        self,
        follower: User,
        followee_username: str
    ) -> Optional[ProfileResponse]:
        """Make the follower follow the user with the given username.
        
        This operation is idempotent - following an already-followed user
        will succeed without error.
        
        Args:
            follower: The user who is following
            followee_username: Username of the user to follow
        
        Returns:
            ProfileResponse of the followed user if found, None otherwise
        """
        # Get the user to follow
        stmt = select(User).where(User.username == followee_username)
        result = await self.db.execute(stmt)
        followee = result.scalar_one_or_none()
        
        if not followee:
            return None
        
        # Check if already following
        already_following = await self.is_following(follower.id, followee.id)
        
        if not already_following:
            # Add the follow relationship
            stmt = follower_association.insert().values(
                follower_id=follower.id,
                followed_id=followee.id
            )
            await self.db.execute(stmt)
            await self.db.commit()
        
        return ProfileResponse(
            username=followee.username,
            bio=followee.bio or "",
            image=followee.image or "https://static.productionready.io/images/smiley-cyrus.jpg",
            following=True
        )
    
    async def unfollow_user(
        self,
        follower: User,
        followee_username: str
    ) -> Optional[ProfileResponse]:
        """Make the follower unfollow the user with the given username.
        
        This operation is idempotent - unfollowing a non-followed user
        will succeed without error.
        
        Args:
            follower: The user who is unfollowing
            followee_username: Username of the user to unfollow
        
        Returns:
            ProfileResponse of the unfollowed user if found, None otherwise
        """
        # Get the user to unfollow
        stmt = select(User).where(User.username == followee_username)
        result = await self.db.execute(stmt)
        followee = result.scalar_one_or_none()
        
        if not followee:
            return None
        
        # Remove the follow relationship if it exists
        stmt = follower_association.delete().where(
            and_(
                follower_association.c.follower_id == follower.id,
                follower_association.c.followed_id == followee.id
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        
        return ProfileResponse(
            username=followee.username,
            bio=followee.bio or "",
            image=followee.image or "https://static.productionready.io/images/smiley-cyrus.jpg",
            following=False
        )
    
    async def is_following(self, follower_id: int, followed_id: int) -> bool:
        """Check if follower_id is following followed_id.
        
        Args:
            follower_id: ID of the potential follower
            followed_id: ID of the potentially followed user
        
        Returns:
            True if following, False otherwise
        """
        stmt = select(exists().where(
            and_(
                follower_association.c.follower_id == follower_id,
                follower_association.c.followed_id == followed_id
            )
        ))
        result = await self.db.execute(stmt)
        return result.scalar() or False
    
    async def is_followed_by(self, user_id: int, follower_id: int) -> bool:
        """Check if user_id is followed by follower_id.
        
        This is the inverse of is_following.
        
        Args:
            user_id: ID of the user
            follower_id: ID of the potential follower
        
        Returns:
            True if followed by, False otherwise
        """
        return await self.is_following(follower_id, user_id)
    
    async def get_followers(self, user_id: int) -> list[User]:
        """Get all users following the given user.
        
        Args:
            user_id: ID of the user
        
        Returns:
            List of User objects who are following this user
        """
        stmt = (
            select(User)
            .join(follower_association, User.id == follower_association.c.follower_id)
            .where(follower_association.c.followed_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_following(self, user_id: int) -> list[User]:
        """Get all users that the given user is following.
        
        Args:
            user_id: ID of the user
        
        Returns:
            List of User objects that this user is following
        """
        stmt = (
            select(User)
            .join(follower_association, User.id == follower_association.c.followed_id)
            .where(follower_association.c.follower_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_following_ids(self, user_id: int) -> list[int]:
        """Get IDs of all users that the given user is following.
        
        Useful for feed generation and other queries that need to check
        if content is from followed users.
        
        Args:
            user_id: ID of the user
        
        Returns:
            List of user IDs that this user is following
        """
        stmt = (
            select(follower_association.c.followed_id)
            .where(follower_association.c.follower_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
