"""Authentication dependencies for FastAPI dependency injection.

Provides reusable dependencies for extracting and validating
the current user from JWT tokens in the Authorization header.
"""

from typing import Optional
import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.service import AuthService

# Configure logging
logger = logging.getLogger(__name__)

# HTTP Bearer token authentication scheme
# auto_error=False allows optional authentication
security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """Dependency to get the current authenticated user.
    
    Validates the JWT token from the Authorization header and returns the user.
    Raises HTTPException if authentication fails.
    
    Args:
        db: Database session (injected)
        credentials: HTTP authorization credentials (injected)
        
    Returns:
        Authenticated user with profile loaded
        
    Raises:
        HTTPException 401: If no credentials, invalid token, expired token, or user not found
        HTTPException 403: If user account is deactivated
        
    Usage:
        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user": current_user.username}
    """
    if not credentials:
        logger.warning("Request made without authentication credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        payload = AuthService.decode_jwt_token(token)
        user_id: int = payload.get("id")
        if user_id is None:
            logger.warning("JWT token missing 'id' field")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        logger.warning("Expired JWT token used")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await AuthService.get_user_by_id(db, user_id)
    
    if user is None:
        logger.warning(f"JWT token references non-existent user ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        logger.warning(f"Deactivated user attempted access: {user.username} (ID: {user.id})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user has been deactivated."
        )
    
    return user


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Dependency to optionally get the current authenticated user.
    
    Returns the user if a valid token is provided, otherwise returns None.
    Does not raise an exception if no credentials are provided or if they're invalid.
    Useful for endpoints that behave differently for authenticated vs anonymous users.
    
    Args:
        db: Database session (injected)
        credentials: HTTP authorization credentials (injected)
        
    Returns:
        Authenticated user with profile loaded if valid token provided, None otherwise
        
    Note:
        - Returns None for missing, expired, or invalid tokens
        - Returns None for deactivated users
        - Does not raise exceptions (silent failure)
        
    Usage:
        @router.get("/optional-auth")
        async def optional_route(current_user: Optional[User] = Depends(get_current_user_optional)):
            if current_user:
                return {"message": f"Hello {current_user.username}"}
            return {"message": "Hello anonymous"}
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    try:
        payload = AuthService.decode_jwt_token(token)
        user_id: int = payload.get("id")
        if user_id is None:
            return None
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
    
    user = await AuthService.get_user_by_id(db, user_id)
    
    if user is None or not user.is_active:
        return None
    
    return user
