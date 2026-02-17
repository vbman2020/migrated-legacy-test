from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional

from app.profiles.models import Profile
from app.profiles.schemas import ProfileBase
from app.auth.models import User
from app.articles.models import Article


class ProfileService:
    """Service for profile operations including follow/unfollow and favorites."""

    DEFAULT_PROFILE_IMAGE = "https://static.productionready.io/images/smiley-cyrus.jpg"

    def __init__(self, db: AsyncSession):
        """Initialize the profile service.
        
        Args:
            db: Database session
        """
        self.db = db

    async def get_profile_by_username(
        self,
        username: str,
        current_user: Optional[User] = None,
    ) -> Optional[ProfileBase]:
        """Get a profile by username.
        
        Args:
            username: Username to look up
            current_user: Currently authenticated user (optional)
        
        Returns:
            ProfileBase with profile data or None if not found
        """
        # Query for the profile with the user relationship
        stmt = (
            select(Profile)
            .join(Profile.user)
            .where(User.username == username)
            .options(selectinload(Profile.user))
            .options(selectinload(Profile.follows))
        )
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        # Check if current user is following this profile
        following = False
        if current_user and current_user.profile:
            following = await self._is_following(
                follower_profile=current_user.profile,
                followee_profile=profile,
            )

        return self._profile_to_schema(profile, following)

    async def follow_user(
        self,
        follower: User,
        username_to_follow: str,
    ) -> Optional[ProfileBase]:
        """Follow a user by username.
        
        Args:
            follower: User who is following
            username_to_follow: Username of user to follow
        
        Returns:
            ProfileBase with updated profile data or None if not found
        """
        # Get the profile to follow
        stmt = (
            select(Profile)
            .join(Profile.user)
            .where(User.username == username_to_follow)
            .options(selectinload(Profile.user))
            .options(selectinload(Profile.follows))
        )
        result = await self.db.execute(stmt)
        followee_profile = result.scalar_one_or_none()

        if not followee_profile:
            return None

        # Get the follower's profile with follows loaded
        stmt = (
            select(Profile)
            .where(Profile.id == follower.profile.id)
            .options(selectinload(Profile.follows))
        )
        result = await self.db.execute(stmt)
        follower_profile = result.scalar_one_or_none()

        if not follower_profile:
            return None

        # Add the follow relationship if not already following
        if followee_profile not in follower_profile.follows:
            follower_profile.follows.append(followee_profile)
            await self.db.commit()
            await self.db.refresh(followee_profile)

        return self._profile_to_schema(followee_profile, following=True)

    async def unfollow_user(
        self,
        follower: User,
        username_to_unfollow: str,
    ) -> Optional[ProfileBase]:
        """Unfollow a user by username.
        
        Args:
            follower: User who is unfollowing
            username_to_unfollow: Username of user to unfollow
        
        Returns:
            ProfileBase with updated profile data or None if not found
        """
        # Get the profile to unfollow
        stmt = (
            select(Profile)
            .join(Profile.user)
            .where(User.username == username_to_unfollow)
            .options(selectinload(Profile.user))
            .options(selectinload(Profile.follows))
        )
        result = await self.db.execute(stmt)
        followee_profile = result.scalar_one_or_none()

        if not followee_profile:
            return None

        # Get the follower's profile with follows loaded
        stmt = (
            select(Profile)
            .where(Profile.id == follower.profile.id)
            .options(selectinload(Profile.follows))
        )
        result = await self.db.execute(stmt)
        follower_profile = result.scalar_one_or_none()

        if not follower_profile:
            return None

        # Remove the follow relationship if currently following
        if followee_profile in follower_profile.follows:
            follower_profile.follows.remove(followee_profile)
            await self.db.commit()
            await self.db.refresh(followee_profile)

        return self._profile_to_schema(followee_profile, following=False)

    async def _is_following(
        self,
        follower_profile: Profile,
        followee_profile: Profile,
    ) -> bool:
        """Check if follower is following followee.
        
        Args:
            follower_profile: Profile of the follower
            followee_profile: Profile being followed
        
        Returns:
            True if following, False otherwise
        """
        # Refresh the follower profile to get the latest follows
        await self.db.refresh(follower_profile, attribute_names=["follows"])
        return followee_profile in follower_profile.follows

    async def is_favorited_by(
        self,
        profile: Profile,
        article: Article,
    ) -> bool:
        """Check if a profile has favorited an article.
        
        Args:
            profile: Profile to check
            article: Article to check
        
        Returns:
            True if favorited, False otherwise
        """
        await self.db.refresh(profile, attribute_names=["favorites"])
        return article in profile.favorites

    async def favorite_article(
        self,
        profile: Profile,
        article: Article,
    ) -> None:
        """Add an article to user's favorites.
        
        Args:
            profile: Profile favoriting the article
            article: Article to favorite
        """
        # Refresh to get current favorites
        await self.db.refresh(profile, attribute_names=["favorites"])
        
        if article not in profile.favorites:
            profile.favorites.append(article)
            await self.db.commit()
            await self.db.refresh(profile)
            await self.db.refresh(article)

    async def unfavorite_article(
        self,
        profile: Profile,
        article: Article,
    ) -> None:
        """Remove an article from user's favorites.
        
        Args:
            profile: Profile unfavoriting the article
            article: Article to unfavorite
        """
        # Refresh to get current favorites
        await self.db.refresh(profile, attribute_names=["favorites"])
        
        if article in profile.favorites:
            profile.favorites.remove(article)
            await self.db.commit()
            await self.db.refresh(profile)
            await self.db.refresh(article)

    def _profile_to_schema(
        self,
        profile: Profile,
        following: bool = False,
    ) -> ProfileBase:
        """Convert a Profile model to ProfileBase schema.
        
        Args:
            profile: Profile model
            following: Whether current user is following this profile
        
        Returns:
            ProfileBase schema
        """
        image = profile.image if profile.image else self.DEFAULT_PROFILE_IMAGE
        
        return ProfileBase(
            username=profile.user.username,
            bio=profile.bio,
            image=image,
            following=following,
        )
