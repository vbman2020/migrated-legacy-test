"""Authentication router for FastAPI endpoints.

Provides endpoints for:
- User registration (POST /api/users)
- User login (POST /api/users/login)
- Current user retrieval (GET /api/user)
- Current user update (PUT /api/user)

All endpoints follow the RealWorld API specification.
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.schemas import (
    UserRegistrationRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponseWrapper,
    UserResponse
)
from app.auth.service import AuthService
from app.auth.dependencies import get_current_user
from app.auth.models import User

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


def user_to_response(user: User) -> UserResponse:
    """Convert a User model to UserResponse schema.
    
    Extracts user and profile data and generates a fresh JWT token.
    
    Args:
        user: User model instance with profile relationship loaded
        
    Returns:
        UserResponse schema with JWT token
        
    Note:
        Profile must be loaded on the user object (using selectinload).
    """
    return UserResponse(
        email=user.email,
        username=user.username,
        bio=user.profile.bio if user.profile else None,
        image=user.profile.image if user.profile else None,
        token=AuthService.generate_jwt_token(user)
    )


@router.post(
    "/users",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register a new user",
    description="Creates a new user account with the provided credentials and returns a JWT token."
)
async def register_user(
    user_data: UserRegistrationRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Register a new user.
    
    Creates a new user account with the provided credentials.
    Returns the created user with a JWT token.
    
    Args:
        user_data: User registration data (email, username, password)
        db: Database session (injected)
        
    Returns:
        User response wrapper with user data and JWT token
        
    Raises:
        HTTPException 422: If email or username already exists
        HTTPException 422: If validation fails (weak password, invalid username)
        
    Example:
        POST /api/users
        {
            "user": {
                "email": "jake@example.com",
                "username": "jake",
                "password": "SecurePass123!"
            }
        }
    """
    logger.info(f"Registration attempt for email: {user_data.user.email}")
    user = await AuthService.create_user(db, user_data.user)
    logger.info(f"User registered successfully: {user.username}")
    return UserResponseWrapper(user=user_to_response(user))


@router.post(
    "/users/login",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Login an existing user",
    description="Authenticates the user with email and password and returns a JWT token."
)
async def login_user(
    user_data: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Login an existing user.
    
    Authenticates the user with email and password.
    Returns the user with a JWT token.
    
    Args:
        user_data: Login credentials (email, password)
        db: Database session (injected)
        
    Returns:
        User response wrapper with user data and JWT token
        
    Raises:
        HTTPException 422: If email/password combination is invalid
        HTTPException 403: If user account is deactivated
        
    Example:
        POST /api/users/login
        {
            "user": {
                "email": "jake@example.com",
                "password": "SecurePass123!"
            }
        }
    """
    logger.info(f"Login attempt for email: {user_data.user.email}")
    user = await AuthService.authenticate_user(
        db,
        user_data.user.email,
        user_data.user.password
    )
    logger.info(f"User logged in successfully: {user.username}")
    return UserResponseWrapper(user=user_to_response(user))


@router.get(
    "/user",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Get current user",
    description="Returns the currently authenticated user's information. Requires a valid JWT token."
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponseWrapper:
    """Get the current authenticated user.
    
    Returns the currently authenticated user's information.
    Requires a valid JWT token in the Authorization header.
    
    Args:
        current_user: Current user (injected from JWT token via dependency)
        
    Returns:
        User response wrapper with user data and JWT token
        
    Raises:
        HTTPException 401: If no token provided or token is invalid/expired
        HTTPException 403: If user account is deactivated
        
    Example:
        GET /api/user
        Authorization: Bearer <jwt-token>
    """
    logger.debug(f"Current user info requested: {current_user.username}")
    return UserResponseWrapper(user=user_to_response(current_user))


@router.put(
    "/user",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Update current user",
    description="Updates the currently authenticated user's information. Requires a valid JWT token."
)
async def update_current_user(
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Update the current authenticated user.
    
    Updates the currently authenticated user's information.
    Requires a valid JWT token in the Authorization header.
    All fields are optional - only provided fields will be updated.
    
    Args:
        user_data: User update data (email, username, password, bio, image)
        current_user: Current user (injected from JWT token via dependency)
        db: Database session (injected)
        
    Returns:
        Updated user response wrapper with user data and JWT token
        
    Raises:
        HTTPException 401: If no token provided or token is invalid/expired
        HTTPException 403: If user account is deactivated
        HTTPException 422: If email or username already taken by another user
        HTTPException 422: If validation fails (weak password, invalid URL)
        
    Example:
        PUT /api/user
        Authorization: Bearer <jwt-token>
        {
            "user": {
                "email": "newemail@example.com",
                "bio": "I work at State Farm",
                "image": "https://example.com/avatar.jpg"
            }
        }
    """
    logger.info(f"User update requested for: {current_user.username}")
    updated_user = await AuthService.update_user(db, current_user, user_data.user)
    logger.info(f"User updated successfully: {updated_user.username}")
    return UserResponseWrapper(user=user_to_response(updated_user))
