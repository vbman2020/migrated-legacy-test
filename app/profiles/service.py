from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.profiles.models import user_follows
from app.profiles.schemas import ProfileResponse


class ProfileService:
    """Service layer for profile operations."""

    DEFAULT_IMAGE = "https://static.productionready.io/images/smiley-cyrus.jpg"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile_by_username(
        self, username: str, current_user: Optional[User] = None
    ) -> Optional[ProfileResponse]:
        """
        Get a user profile by username.
        
        Args:
            username: The username to look up
            current_user: The currently authenticated user (optional)
            
        Returns:
            ProfileResponse if user found, None otherwise
        """
        # Query the user
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Check if current user is following this user
        following = False
        if current_user:
            following = await self._is_following(current_user.id, user.id)
        
        # Get the image or use default
        image = user.image if user.image else self.DEFAULT_IMAGE
        
        return ProfileResponse(
            username=user.username,
            bio=user.bio or "",
            image=image,
            following=following,
        )

    async def follow_user(
        self, current_user: User, username: str
    ) -> Optional[ProfileResponse]:
        """
        Follow a user.
        
        Args:
            current_user: The user who wants to follow
            username: The username of the user to follow
            
        Returns:
            ProfileResponse of the followed user if found, None otherwise
        """
        # Get the user to follow
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        user_to_follow = result.scalar_one_or_none()
        
        if not user_to_follow:
            return None
        
        # Check if already following
        is_following = await self._is_following(current_user.id, user_to_follow.id)
        
        if not is_following:
            # Add the follow relationship
            stmt = user_follows.insert().values(
                follower_id=current_user.id,
                followee_id=user_to_follow.id
            )
            await self.db.execute(stmt)
            await self.db.commit()
        
        # Get the image or use default
        image = user_to_follow.image if user_to_follow.image else self.DEFAULT_IMAGE
        
        return ProfileResponse(
            username=user_to_follow.username,
            bio=user_to_follow.bio or "",
            image=image,
            following=True,
        )

    async def unfollow_user(
        self, current_user: User, username: str
    ) -> Optional[ProfileResponse]:
        """
        Unfollow a user.
        
        Args:
            current_user: The user who wants to unfollow
            username: The username of the user to unfollow
            
        Returns:
            ProfileResponse of the unfollowed user if found, None otherwise
        """
        # Get the user to unfollow
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        user_to_unfollow = result.scalar_one_or_none()
        
        if not user_to_unfollow:
            return None
        
        # Check if currently following
        is_following = await self._is_following(current_user.id, user_to_unfollow.id)
        
        if is_following:
            # Remove the follow relationship
            stmt = user_follows.delete().where(
                (user_follows.c.follower_id == current_user.id) &
                (user_follows.c.followee_id == user_to_unfollow.id)
            )
            await self.db.execute(stmt)
            await self.db.commit()
        
        # Get the image or use default
        image = user_to_unfollow.image if user_to_unfollow.image else self.DEFAULT_IMAGE
        
        return ProfileResponse(
            username=user_to_unfollow.username,
            bio=user_to_unfollow.bio or "",
            image=image,
            following=False,
        )

    async def _is_following(
        self, follower_id: int, followee_id: int
    ) -> bool:
        """
        Check if follower_id is following followee_id.
        
        Args:
            follower_id: The ID of the user who might be following
            followee_id: The ID of the user being followed
            
        Returns:
            True if follower is following followee, False otherwise
        """
        query = select(user_follows).where(
            (user_follows.c.follower_id == follower_id) &
            (user_follows.c.followee_id == followee_id)
        )
        result = await self.db.execute(query)
        return result.first() is not None
