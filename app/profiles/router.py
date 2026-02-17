from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.profiles.schemas import ProfileResponseWrapper
from app.profiles.service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("/{username}", response_model=ProfileResponseWrapper)
async def get_profile(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)] = None,
):
    """
    Get a user profile by username.
    
    Returns profile information including username, bio, image, and whether
    the current user is following this profile.
    
    - **username**: The username of the profile to retrieve
    - **Authorization**: Optional - if provided, the response will indicate if the current user follows this profile
    """
    service = ProfileService(db)
    profile = await service.get_profile_by_username(username, current_user)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username does not exist.",
        )
    
    return ProfileResponseWrapper(profile=profile)


@router.post("/{username}/follow", response_model=ProfileResponseWrapper, status_code=status.HTTP_200_OK)
async def follow_user(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Follow a user.
    
    The authenticated user will follow the user specified by username.
    Returns the followed user's profile with following set to true.
    
    - **username**: The username of the user to follow
    - **Authorization**: Required - JWT token in the format "Token {jwt}"
    """
    service = ProfileService(db)
    
    # Check if user is trying to follow themselves
    if current_user.username == username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You can not follow yourself.",
        )
    
    profile = await service.follow_user(current_user, username)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username was not found.",
        )
    
    return ProfileResponseWrapper(profile=profile)


@router.delete("/{username}/follow", response_model=ProfileResponseWrapper)
async def unfollow_user(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Unfollow a user.
    
    The authenticated user will unfollow the user specified by username.
    Returns the unfollowed user's profile with following set to false.
    
    - **username**: The username of the user to unfollow
    - **Authorization**: Required - JWT token in the format "Token {jwt}"
    """
    service = ProfileService(db)
    profile = await service.unfollow_user(current_user, username)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username was not found.",
        )
    
    return ProfileResponseWrapper(profile=profile)
