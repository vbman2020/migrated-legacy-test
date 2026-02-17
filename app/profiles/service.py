from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from typing import Optional

from app.profiles.models import Profile
from app.profiles.schemas import ProfileSchema
from app.auth.models import User


class ProfileService:
    """Service class for profile operations."""

    @staticmethod
    async def get_profile_by_username(
        db: AsyncSession,
        username: str,
        current_user: Optional[User] = None
    ) -> ProfileSchema:
        """Get a user profile by username.
        
        Args:
            db: Database session
            username: Username to look up
            current_user: Currently authenticated user (optional)
            
        Returns:
            ProfileSchema with user profile data
            
        Raises:
            HTTPException: If profile not found
        """
        # Query for user with profile
        query = (
            select(User)
            .options(selectinload(User.profile).selectinload(Profile.followers))
            .where(User.username == username)
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not user.profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A profile with this username does not exist."
            )

        profile = user.profile
        
        # Determine if current user is following this profile
        following = False
        if current_user and current_user.profile:
            # Check if current user's profile is in the followers list
            following = any(
                follower.id == current_user.profile.id 
                for follower in profile.followers
            )

        # Get image URL with default fallback
        image_url = profile.image if profile.image else "https://static.productionready.io/images/smiley-cyrus.jpg"

        return ProfileSchema(
            username=user.username,
            bio=profile.bio or "",
            image=image_url,
            following=following
        )

    @staticmethod
    async def follow_user(
        db: AsyncSession,
        username: str,
        current_user: User
    ) -> ProfileSchema:
        """Follow a user.
        
        Args:
            db: Database session
            username: Username to follow
            current_user: Currently authenticated user
            
        Returns:
            ProfileSchema of the followed user
            
        Raises:
            HTTPException: If profile not found or user tries to follow themselves
        """
        # Get the user to follow
        query = (
            select(User)
            .options(selectinload(User.profile).selectinload(Profile.followers))
            .where(User.username == username)
        )
        result = await db.execute(query)
        user_to_follow = result.scalar_one_or_none()

        if not user_to_follow or not user_to_follow.profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A profile with this username was not found."
            )

        # Check if user is trying to follow themselves
        if current_user.id == user_to_follow.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="You can not follow yourself."
            )

        # Get current user's profile with following relationship loaded
        query = (
            select(Profile)
            .options(selectinload(Profile.following))
            .where(Profile.user_id == current_user.id)
        )
        result = await db.execute(query)
        follower_profile = result.scalar_one_or_none()

        if not follower_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Current user profile not found."
            )

        # Add to following if not already following
        if user_to_follow.profile not in follower_profile.following:
            follower_profile.following.append(user_to_follow.profile)
            await db.commit()
            await db.refresh(follower_profile)

        # Refresh to get updated followers
        await db.refresh(user_to_follow.profile)

        # Get image URL with default fallback
        image_url = user_to_follow.profile.image if user_to_follow.profile.image else "https://static.productionready.io/images/smiley-cyrus.jpg"

        return ProfileSchema(
            username=user_to_follow.username,
            bio=user_to_follow.profile.bio or "",
            image=image_url,
            following=True
        )

    @staticmethod
    async def unfollow_user(
        db: AsyncSession,
        username: str,
        current_user: User
    ) -> ProfileSchema:
        """Unfollow a user.
        
        Args:
            db: Database session
            username: Username to unfollow
            current_user: Currently authenticated user
            
        Returns:
            ProfileSchema of the unfollowed user
            
        Raises:
            HTTPException: If profile not found
        """
        # Get the user to unfollow
        query = (
            select(User)
            .options(selectinload(User.profile).selectinload(Profile.followers))
            .where(User.username == username)
        )
        result = await db.execute(query)
        user_to_unfollow = result.scalar_one_or_none()

        if not user_to_unfollow or not user_to_unfollow.profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A profile with this username was not found."
            )

        # Get current user's profile with following relationship loaded
        query = (
            select(Profile)
            .options(selectinload(Profile.following))
            .where(Profile.user_id == current_user.id)
        )
        result = await db.execute(query)
        follower_profile = result.scalar_one_or_none()

        if not follower_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Current user profile not found."
            )

        # Remove from following if currently following
        if user_to_unfollow.profile in follower_profile.following:
            follower_profile.following.remove(user_to_unfollow.profile)
            await db.commit()
            await db.refresh(follower_profile)

        # Refresh to get updated followers
        await db.refresh(user_to_unfollow.profile)

        # Get image URL with default fallback
        image_url = user_to_unfollow.profile.image if user_to_unfollow.profile.image else "https://static.productionready.io/images/smiley-cyrus.jpg"

        return ProfileSchema(
            username=user_to_unfollow.username,
            bio=user_to_unfollow.profile.bio or "",
            image=image_url,
            following=False
        )
