from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, get_optional_user
from app.auth.models import User
from app.profiles.schemas import ProfileResponse
from app.profiles.service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("/{username}", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def get_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get a user profile by username.
    
    This endpoint can be accessed by both authenticated and unauthenticated users.
    If authenticated, the response includes whether the current user is following this profile.
    
    Args:
        username: The username of the profile to retrieve
        db: Database session
        current_user: Currently authenticated user (optional)
        
    Returns:
        ProfileResponse containing the user profile
        
    Raises:
        HTTPException 404: If profile not found
    """
    profile = await ProfileService.get_profile_by_username(db, username, current_user)
    return ProfileResponse(profile=profile)


@router.post(
    "/{username}/follow",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED
)
async def follow_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Follow a user.
    
    Requires authentication. The current user will follow the user specified by username.
    
    Args:
        username: The username of the user to follow
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        ProfileResponse of the followed user with following=True
        
    Raises:
        HTTPException 401: If not authenticated
        HTTPException 404: If profile not found
        HTTPException 422: If user tries to follow themselves
    """
    profile = await ProfileService.follow_user(db, username, current_user)
    return ProfileResponse(profile=profile)


@router.delete(
    "/{username}/follow",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK
)
async def unfollow_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unfollow a user.
    
    Requires authentication. The current user will unfollow the user specified by username.
    
    Args:
        username: The username of the user to unfollow
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        ProfileResponse of the unfollowed user with following=False
        
    Raises:
        HTTPException 401: If not authenticated
        HTTPException 404: If profile not found
    """
    profile = await ProfileService.unfollow_user(db, username, current_user)
    return ProfileResponse(profile=profile)
