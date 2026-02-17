"""FastAPI router for authentication endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    UserRegistrationRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponse,
    UserResponseWrapper
)
from app.auth.service import auth_service
from app.database import get_db


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/users",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register a new user",
    description="Register a new user account with username, email, and password. "
                "Creates a user profile automatically."
)
async def register_user(
    request: UserRegistrationRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Register a new user.
    
    Creates a new user account with the provided credentials and automatically
    creates an associated profile. Returns the user data with a JWT token.
    
    Args:
        request: User registration data containing username, email, and password.
        db: Database session.
    
    Returns:
        UserResponseWrapper: Created user data with JWT token.
    
    Raises:
        HTTPException: 422 if username or email already exists.
        HTTPException: 422 if validation fails (weak password, invalid email, etc.).
    """
    # Check if email already exists
    existing_user = await auth_service.get_user_by_email(db, request.user.email)
    if existing_user:
        logger.warning(f"Registration attempt with existing email: {request.user.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User with this email already exists"
        )
    
    # Check if username already exists
    existing_user = await auth_service.get_user_by_username(db, request.user.username)
    if existing_user:
        logger.warning(f"Registration attempt with existing username: {request.user.username}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User with this username already exists"
        )
    
    try:
        # Create user with associated profile
        user = await auth_service.create_user(
            db=db,
            username=request.user.username,
            email=request.user.email,
            password=request.user.password
        )
    except IntegrityError:
        # Handle race condition where user was created between checks
        logger.error(f"Race condition in user registration: {request.user.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User with this email or username already exists"
        )
    except ValueError as e:
        # Handle password validation errors
        logger.warning(f"Invalid password in registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in user registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )
    
    # Generate JWT token
    try:
        token = auth_service.create_access_token(user.id)
    except ValueError as e:
        logger.error(f"Token creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token"
        )
    
    # Build response
    user_response = UserResponse(
        email=user.email,
        username=user.username,
        bio=user.profile.bio if user.profile else "",
        image=user.profile.image if user.profile else None,
        token=token
    )
    
    logger.info(f"User registered successfully: {user.email}")
    return UserResponseWrapper(user=user_response)


@router.post(
    "/users/login",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Login existing user",
    description="Authenticate with email and password to receive a JWT token. "
                "Token must be included in Authorization header for protected endpoints."
)
async def login_user(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Authenticate a user and return a JWT token.
    
    Validates the user's credentials and returns a JWT token for accessing
    protected endpoints. Generic error messages prevent user enumeration.
    
    Args:
        request: User login credentials (email and password).
        db: Database session.
    
    Returns:
        UserResponseWrapper: User data with JWT token.
    
    Raises:
        HTTPException: 422 if authentication fails (invalid credentials or inactive account).
    """
    user = await auth_service.authenticate_user(
        db=db,
        email=request.user.email,
        password=request.user.password
    )
    
    if not user:
        # Generic error message to prevent user enumeration
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A user with this email and password was not found."
        )
    
    # Generate JWT token
    try:
        token = auth_service.create_access_token(user.id)
    except ValueError as e:
        logger.error(f"Token creation failed for user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token"
        )
    
    # Build response
    user_response = UserResponse(
        email=user.email,
        username=user.username,
        bio=user.profile.bio if user.profile else "",
        image=user.profile.image if user.profile else None,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.get(
    "/user",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Get current user",
    description="Get the currently authenticated user's information. "
                "Requires valid JWT token in Authorization header."
)
async def get_current_user_info(
    current_user = Depends(get_current_user)
) -> UserResponseWrapper:
    """Get the current authenticated user's information.
    
    Returns the user profile data along with a fresh JWT token.
    Requires authentication via Bearer token in Authorization header.
    
    Args:
        current_user: Currently authenticated user from dependency.
    
    Returns:
        UserResponseWrapper: Current user data with fresh JWT token.
    
    Raises:
        HTTPException: 401 if not authenticated or token invalid.
        HTTPException: 403 if user account is inactive.
    """
    # Generate fresh token
    try:
        token = auth_service.create_access_token(current_user.id)
    except ValueError as e:
        logger.error(f"Token creation failed for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token"
        )
    
    # Build response
    user_response = UserResponse(
        email=current_user.email,
        username=current_user.username,
        bio=current_user.profile.bio if current_user.profile else "",
        image=current_user.profile.image if current_user.profile else None,
        token=token
    )
    
    return UserResponseWrapper(user=user_response)


@router.put(
    "/user",
    response_model=UserResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Update current user",
    description="Update the currently authenticated user's information including "
                "email, username, password, bio, and profile image. "
                "Requires valid JWT token in Authorization header."
)
async def update_current_user(
    request: UserUpdateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponseWrapper:
    """Update the current authenticated user's information.
    
    Allows updating user credentials and profile information.
    All fields are optional - only provided fields will be updated.
    
    Args:
        request: User update data (email, username, password, bio, image).
        current_user: Currently authenticated user from dependency.
        db: Database session.
    
    Returns:
        UserResponseWrapper: Updated user data with fresh JWT token.
    
    Raises:
        HTTPException: 401 if not authenticated or token invalid.
        HTTPException: 403 if user account is inactive.
        HTTPException: 422 if email or username is already taken by another user.
        HTTPException: 422 if validation fails (weak password, invalid email, etc.).
    """
    # Check if email is being updated and if it's already taken
    if request.user.email and request.user.email != current_user.email:
        existing_user = await auth_service.get_user_by_email(db, request.user.email)
        if existing_user:
            logger.warning(
                f"User {current_user.email} attempted to change to existing email: {request.user.email}"
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="User with this email already exists"
            )
    
    # Check if username is being updated and if it's already taken
    if request.user.username and request.user.username != current_user.username:
        existing_user = await auth_service.get_user_by_username(db, request.user.username)
        if existing_user:
            logger.warning(
                f"User {current_user.email} attempted to change to existing username: {request.user.username}"
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="User with this username already exists"
            )
    
    try:
        # Update user and profile
        updated_user = await auth_service.update_user(
            db=db,
            user=current_user,
            email=request.user.email,
            username=request.user.username,
            password=request.user.password,
            bio=request.user.bio,
            image=request.user.image
        )
    except IntegrityError:
        # Handle race condition
        logger.error(f"Race condition in user update: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User with this email or username already exists"
        )
    except ValueError as e:
        # Handle validation errors
        logger.warning(f"Invalid data in user update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in user update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user account"
        )
    
    # Generate fresh token
    try:
        token = auth_service.create_access_token(updated_user.id)
    except ValueError as e:
        logger.error(f"Token creation failed for user {updated_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token"
        )
    
    # Build response
    user_response = UserResponse(
        email=updated_user.email,
        username=updated_user.username,
        bio=updated_user.profile.bio if updated_user.profile else "",
        image=updated_user.profile.image if updated_user.profile else None,
        token=token
    )
    
    logger.info(f"User updated successfully: {updated_user.email}")
    return UserResponseWrapper(user=user_response)
