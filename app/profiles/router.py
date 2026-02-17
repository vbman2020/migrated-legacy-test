from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.models import User
from app.profiles.schemas import ProfileResponse
from app.profiles.service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get(
    "/{username}",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a profile",
    description="Get a user profile by username. Authentication is optional.",
)
async def get_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> ProfileResponse:
    """Get a user profile by username.
    
    Args:
        username: The username of the profile to retrieve
        db: Database session
        current_user: Currently authenticated user (optional)
    
    Returns:
        ProfileResponse with profile data
    
    Raises:
        HTTPException: 404 if profile not found
    """
    service = ProfileService(db)
    profile_data = await service.get_profile_by_username(
        username=username,
        current_user=current_user,
    )
    
    if not profile_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username does not exist.",
        )
    
    return ProfileResponse(profile=profile_data)


@router.post(
    "/{username}/follow",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Follow a user",
    description="Follow a user by username. Requires authentication.",
)
async def follow_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    """Follow a user by username.
    
    Args:
        username: The username of the user to follow
        db: Database session
        current_user: Currently authenticated user
    
    Returns:
        ProfileResponse with updated profile data
    
    Raises:
        HTTPException: 404 if profile not found
        HTTPException: 422 if trying to follow yourself
    """
    service = ProfileService(db)
    
    # Check if trying to follow yourself
    if current_user.username == username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You can not follow yourself.",
        )
    
    profile_data = await service.follow_user(
        follower=current_user,
        username_to_follow=username,
    )
    
    if not profile_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username was not found.",
        )
    
    return ProfileResponse(profile=profile_data)


@router.delete(
    "/{username}/follow",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Unfollow a user",
    description="Unfollow a user by username. Requires authentication.",
)
async def unfollow_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    """Unfollow a user by username.
    
    Args:
        username: The username of the user to unfollow
        db: Database session
        current_user: Currently authenticated user
    
    Returns:
        ProfileResponse with updated profile data
    
    Raises:
        HTTPException: 404 if profile not found
    """
    service = ProfileService(db)
    
    profile_data = await service.unfollow_user(
        follower=current_user,
        username_to_unfollow=username,
    )
    
    if not profile_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A profile with this username was not found.",
        )
    
    return ProfileResponse(profile=profile_data)
