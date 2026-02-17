"""Profile API routes.

Provides endpoints for:
- Retrieving user profiles
- Following/unfollowing users
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.service import get_current_user, get_current_user_optional
from app.profiles.schemas import ProfileResponseWrapper
from app.profiles.service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("/{username}", response_model=ProfileResponseWrapper)
async def get_profile(
    username: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Get a user profile by username.
    
    This endpoint can be accessed both authenticated and unauthenticated.
    If authenticated, the 'following' field will indicate whether the current
    user is following this profile.
    
    Args:
        username: The username of the profile to retrieve
        current_user: Optional authenticated user
        db: Database session
    
    Returns:
        ProfileResponseWrapper containing the profile data
    
    Raises:
        HTTPException 404: If profile with username does not exist
    """
    profile_service = ProfileService(db)
    profile = await profile_service.get_profile_by_username(username, current_user)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username does not exist."
        )
    
    return ProfileResponseWrapper(profile=profile)


@router.post("/{username}/follow", response_model=ProfileResponseWrapper, status_code=status.HTTP_200_OK)
async def follow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Follow a user.
    
    Requires authentication. Users cannot follow themselves.
    Returns HTTP 200 on success (even if already following).
    
    Args:
        username: The username of the user to follow
        current_user: Authenticated user making the request
        db: Database session
    
    Returns:
        ProfileResponseWrapper with following=True
    
    Raises:
        HTTPException 404: If user to follow does not exist
        HTTPException 422: If trying to follow yourself
    """
    if current_user.username == username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You can not follow yourself."
        )
    
    profile_service = ProfileService(db)
    profile = await profile_service.follow_user(current_user, username)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username was not found."
        )
    
    return ProfileResponseWrapper(profile=profile)


@router.delete("/{username}/follow", response_model=ProfileResponseWrapper)
async def unfollow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unfollow a user.
    
    Requires authentication.
    Returns HTTP 200 on success (even if not currently following).
    
    Args:
        username: The username of the user to unfollow
        current_user: Authenticated user making the request
        db: Database session
    
    Returns:
        ProfileResponseWrapper with following=False
    
    Raises:
        HTTPException 404: If user to unfollow does not exist
    """
    profile_service = ProfileService(db)
    profile = await profile_service.unfollow_user(current_user, username)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username was not found."
        )
    
    return ProfileResponseWrapper(profile=profile)
