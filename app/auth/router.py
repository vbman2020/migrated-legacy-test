"""FastAPI router for authentication endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    UserRegistrationRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponseWrapper,
    UserResponse
)
from app.auth.service import AuthService
from app.auth.models import User
from app.dependencies import get_db
from app.core.security import create_access_token


router = APIRouter()


async def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get the current authenticated user.
    
    Validates the Authorization header format and JWT token.
    Ensures the user exists and is active.
    
    Args:
        authorization: Authorization header containing JWT token (format: "Token <jwt>")
        db: Database session
        
    Returns:
        Current authenticated User object
        
    Raises:
        HTTPException 401: If token is missing, invalid, or expired
        HTTPException 403: If user account is deactivated
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )
    
    # Parse the authorization header (format: "Token <jwt>")
    parts = authorization.split()
    
    if len(parts) != 2 or parts[0].lower() != "token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication header format. Expected 'Token <jwt>'."
        )
    
    token = parts[1]
    
    user = await AuthService.get_current_user_from_token(db, token)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )
    
    return user


async def get_current_user_optional(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Dependency to optionally get the current authenticated user.
    
    Used for endpoints that work differently for authenticated vs anonymous users.
    Does not raise exceptions if authentication fails.
    
    Args:
        authorization: Authorization header containing JWT token
        db: Database session
        
    Returns:
        Current authenticated User object or None if not authenticated
    """
    if not authorization:
        return None
    
    parts = authorization.split()
    
    if len(parts) != 2 or parts[0].lower() != "token":
        return None
    
    token = parts[1]
    user = await AuthService.get_current_user_from_token(db, token)
    
    return user if user and user.is_active else None


@router.post("/users", response_model=UserResponseWrapper, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistrationRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Register a new user.
    
    Creates a new user account with the provided credentials.
    Validates that email and username are unique.
    Returns a JWT token for immediate authentication.
    
    Args:
        user_data: Registration data containing email, username, and password
        db: Database session
        
    Returns:
        UserResponseWrapper containing the created user with JWT token
        
    Raises:
        HTTPException 422: If email or username already exists
    """
    # Check if email already exists
    existing_user = await AuthService.get_user_by_email(db, user_data.user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email already exists."
        )
    
    # Check if username already exists
    existing_user = await AuthService.get_user_by_username(db, user_data.user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this username already exists."
        )
    
    # Create the user
    user = await AuthService.create_user(db, user_data.user)
    
    # Generate token for the new user
    token = create_access_token(user.id)
    
    # Build response
    user_response = UserResponse(
        email=user.email,
        username=user.username,
        bio=user.profile.bio if user.profile else None,
        image=user.profile.image if user.profile else None,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.post("/users/login", response_model=UserResponseWrapper)
async def login_user(
    login_data: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Authenticate a user and return a JWT token.
    
    Validates credentials and returns user information with a fresh JWT token.
    
    Args:
        login_data: Login credentials containing email and password
        db: Database session
        
    Returns:
        UserResponseWrapper containing the authenticated user with JWT token
        
    Raises:
        HTTPException 422: If credentials are invalid or user is deactivated
    """
    user = await AuthService.authenticate_user(
        db,
        login_data.user.email,
        login_data.user.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email and password was not found."
        )
    
    # Explicitly check if user is active (already checked in authenticate_user, but be explicit)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user has been deactivated."
        )
    
    # Generate fresh token
    token = create_access_token(user.id)
    
    # Build response
    user_response = UserResponse(
        email=user.email,
        username=user.username,
        bio=user.profile.bio if user.profile else None,
        image=user.profile.image if user.profile else None,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.get("/user", response_model=UserResponseWrapper)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponseWrapper:
    """Get the current authenticated user's information.
    
    Requires authentication via JWT token in Authorization header.
    
    Args:
        current_user: Current authenticated user from dependency
        
    Returns:
        UserResponseWrapper containing the current user with a fresh JWT token
    """
    # Generate fresh token
    token = create_access_token(current_user.id)
    
    user_response = UserResponse(
        email=current_user.email,
        username=current_user.username,
        bio=current_user.profile.bio if current_user.profile else None,
        image=current_user.profile.image if current_user.profile else None,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.put("/user", response_model=UserResponseWrapper)
async def update_current_user(
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Update the current authenticated user's information.
    
    Allows updating email, username, password, bio, and image.
    All fields are optional - only provided fields will be updated.
    Validates that new email/username don't conflict with other users.
    
    Args:
        user_data: Update data with optional fields
        current_user: Current authenticated user from dependency
        db: Database session
        
    Returns:
        UserResponseWrapper containing the updated user with a fresh JWT token
        
    Raises:
        HTTPException 422: If email or username conflicts with existing users
    """
    # Check if email is being updated and already exists
    if user_data.user.email and user_data.user.email != current_user.email:
        existing_user = await AuthService.get_user_by_email(db, user_data.user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this email already exists."
            )
    
    # Check if username is being updated and already exists
    if user_data.user.username and user_data.user.username != current_user.username:
        existing_user = await AuthService.get_user_by_username(db, user_data.user.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this username already exists."
            )
    
    # Update the user
    updated_user = await AuthService.update_user(db, current_user, user_data.user)
    
    # Generate fresh token
    token = create_access_token(updated_user.id)
    
    # Build response
    user_response = UserResponse(
        email=updated_user.email,
        username=updated_user.username,
        bio=updated_user.profile.bio if updated_user.profile else None,
        image=updated_user.profile.image if updated_user.profile else None,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)
