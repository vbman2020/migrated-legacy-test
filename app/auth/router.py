"""FastAPI router for authentication endpoints.

Implements RealWorld API specification for user authentication:
    - POST /api/users - Register new user
    - POST /api/users/login - Login existing user
    - GET /api/user - Get current authenticated user
    - PUT /api/user - Update current authenticated user

All endpoints follow the RealWorld API format with requests/responses
wrapped in a 'user' object.
"""

from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.auth.schemas import (
    UserCreateWrapper,
    UserLoginWrapper,
    UserResponseWrapper,
    UserUpdateWrapper,
    UserResponse,
)
from app.auth.service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
    generate_token_for_user,
    update_user,
)
from app.auth.models import User
from app.dependencies import get_db, get_current_user

# Configure logging for authentication events
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["authentication"])


@router.post(
    "/users",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with email, username, and password. Returns user data with JWT token.",
    responses={
        201: {
            "description": "User successfully registered",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "email": "user@example.com",
                            "username": "johndoe",
                            "bio": None,
                            "image": None,
                            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                        }
                    }
                }
            }
        },
        422: {
            "description": "Validation error or user already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A user with this email already exists."
                    }
                }
            }
        }
    }
)
async def register_user(
    user_data: UserCreateWrapper,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> UserResponseWrapper:
    """Register a new user.
    
    Validates that email and username are unique, then creates new user
    with hashed password. Returns user data with JWT authentication token.
    
    Args:
        user_data: User registration data wrapped in user object (RealWorld API format)
        db: Database session (injected dependency)
        
    Returns:
        UserResponseWrapper containing user data and JWT token
        
    Raises:
        HTTPException 422: If email or username already exists
        HTTPException 422: If validation fails (handled by Pydantic)
    """
    user_create = user_data.user
    
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_create.email)
    if existing_user:
        logger.info(f"Registration attempt with existing email: {user_create.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email already exists."
        )
    
    # Check if username already exists
    existing_user = await get_user_by_username(db, user_create.username)
    if existing_user:
        logger.info(f"Registration attempt with existing username: {user_create.username}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this username already exists."
        )
    
    # Create new user
    try:
        new_user = await create_user(db, user_create)
        logger.info(f"Successfully registered user: {new_user.username} (ID: {new_user.id})")
    except IntegrityError as e:
        # Race condition: user was created between our checks and the insert
        logger.warning(f"Race condition during user registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email or username already exists."
        )
    
    # Generate JWT token
    token = generate_token_for_user(new_user)
    
    # Build response
    user_response = UserResponse(
        email=new_user.email,
        username=new_user.username,
        bio=new_user.bio,
        image=new_user.image,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.post(
    "/users/login",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    summary="Login user",
    description="Authenticate user with email and password. Returns user data with JWT token.",
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "email": "user@example.com",
                            "username": "johndoe",
                            "bio": "I love coding!",
                            "image": "https://example.com/avatar.jpg",
                            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                        }
                    }
                }
            }
        },
        422: {
            "description": "Invalid credentials or inactive user",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A user with this email and password was not found."
                    }
                }
            }
        }
    }
)
async def login_user(
    user_data: UserLoginWrapper,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> UserResponseWrapper:
    """Login an existing user.
    
    Authenticates user credentials and returns user data with JWT token.
    Uses timing-safe password comparison to prevent timing attacks.
    Implements account lockout after repeated failed attempts.
    
    Args:
        user_data: User login credentials wrapped in user object (RealWorld API format)
        db: Database session (injected dependency)
        
    Returns:
        UserResponseWrapper containing user data and JWT token
        
    Raises:
        HTTPException 422: If credentials are invalid, user is inactive, or account is locked
        
    Security Notes:
        - Does not reveal whether email or password was incorrect
        - Performs constant-time password verification
        - Implements account lockout after 5 failed attempts
        - Logs failed authentication attempts for monitoring
    """
    user_login = user_data.user
    
    # Authenticate user (timing-safe password verification + account lockout)
    user = await authenticate_user(db, user_login.email, user_login.password)
    
    if not user:
        logger.info(f"Failed login attempt for email: {user_login.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email and password was not found."
        )
    
    # Check if user is active (redundant check since authenticate_user does this, but explicit is good)
    if not user.is_active:
        logger.warning(f"Login attempt for deactivated user: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This user has been deactivated."
        )
    
    # Generate JWT token
    token = generate_token_for_user(user)
    logger.info(f"Successful login for user: {user.username} (ID: {user.id})")
    
    # Build response
    user_response = UserResponse(
        email=user.email,
        username=user.username,
        bio=user.bio,
        image=user.image,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.get(
    "/user",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get the currently authenticated user's information. Requires authentication.",
    responses={
        200: {
            "description": "Current user retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "email": "user@example.com",
                            "username": "johndoe",
                            "bio": "I love coding!",
                            "image": "https://example.com/avatar.jpg",
                            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated or invalid token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials"
                    }
                }
            }
        }
    }
)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserResponseWrapper:
    """Get current authenticated user.
    
    Returns user data for the currently authenticated user based on JWT token.
    Generates a fresh token in the response.
    
    Args:
        current_user: Currently authenticated user from JWT token (injected dependency)
        
    Returns:
        UserResponseWrapper containing user data and fresh JWT token
        
    Raises:
        HTTPException 401: If token is invalid or expired (handled by get_current_user dependency)
    """
    # Generate fresh token
    token = generate_token_for_user(current_user)
    
    # Build response
    user_response = UserResponse(
        email=current_user.email,
        username=current_user.username,
        bio=current_user.bio,
        image=current_user.image,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.put(
    "/user",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    summary="Update current user",
    description="Update the currently authenticated user's information. Requires authentication.",
    responses={
        200: {
            "description": "User updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "email": "newemail@example.com",
                            "username": "newusername",
                            "bio": "Updated bio",
                            "image": "https://example.com/new-avatar.jpg",
                            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated or invalid token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials"
                    }
                }
            }
        },
        422: {
            "description": "Validation error or username/email already taken",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A user with this email already exists."
                    }
                }
            }
        }
    }
)
async def update_current_user(
    user_data: UserUpdateWrapper,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> UserResponseWrapper:
    """Update current authenticated user.
    
    Allows user to update their profile information including:
        - Email (validated for uniqueness)
        - Username (validated for uniqueness)
        - Password (re-hashed with bcrypt)
        - Bio (sanitized for XSS prevention)
        - Image URL (validated format, no data: or javascript: URLs)
    
    Args:
        user_data: User update data wrapped in user object (RealWorld API format)
        current_user: Currently authenticated user from JWT token (injected dependency)
        db: Database session (injected dependency)
        
    Returns:
        UserResponseWrapper containing updated user data and fresh JWT token
        
    Raises:
        HTTPException 401: If token is invalid or expired (handled by get_current_user dependency)
        HTTPException 422: If email or username already taken by another user
        HTTPException 422: If validation fails (handled by Pydantic)
        
    Note:
        Only fields provided in the request will be updated.
        Token is regenerated if email or username changes.
    """
    user_update = user_data.user
    
    # Check if new email is already taken by another user
    if user_update.email is not None and user_update.email != current_user.email:
        existing_user = await get_user_by_email(db, user_update.email)
        if existing_user and existing_user.id != current_user.id:
            logger.info(f"User {current_user.id} attempted to update to existing email: {user_update.email}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this email already exists."
            )
    
    # Check if new username is already taken by another user
    if user_update.username is not None and user_update.username != current_user.username:
        existing_user = await get_user_by_username(db, user_update.username)
        if existing_user and existing_user.id != current_user.id:
            logger.info(f"User {current_user.id} attempted to update to existing username: {user_update.username}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this username already exists."
            )
    
    # Update user
    try:
        updated_user = await update_user(db, current_user, user_update)
        logger.info(f"Successfully updated user: {updated_user.username} (ID: {updated_user.id})")
    except IntegrityError as e:
        # Race condition: username/email was taken between our check and the update
        logger.warning(f"Race condition during user update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email or username already exists."
        )
    
    # Generate fresh token (important if email or username changed)
    token = generate_token_for_user(updated_user)
    
    # Build response
    user_response = UserResponse(
        email=updated_user.email,
        username=updated_user.username,
        bio=updated_user.bio,
        image=updated_user.image,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)
