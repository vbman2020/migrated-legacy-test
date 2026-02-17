"""FastAPI dependencies for authentication."""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import auth_service
from app.database import get_db


logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get the current authenticated user.
    
    This dependency extracts and validates the JWT token from the Authorization header,
    and returns the authenticated user object. Required for protected endpoints.
    
    Args:
        db: Database session from dependency.
        credentials: HTTP Bearer credentials from Authorization header.
    
    Returns:
        User: The authenticated user object.
    
    Raises:
        HTTPException: 401 if not authenticated or token invalid.
        HTTPException: 403 if user account is inactive.
    """
    if credentials is None:
        logger.debug("No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    token_data = auth_service.decode_access_token(token)
    
    if token_data is None:
        logger.warning("Invalid token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Convert token subject (user_id as string) to int
    try:
        user_id = int(token_data.sub)
    except (ValueError, TypeError):
        logger.error(f"Invalid token subject: {token_data.sub}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await auth_service.get_user_by_id(db, user_id)
    
    if user is None:
        logger.warning(f"User not found for token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        logger.warning(f"Inactive user attempted access: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get the current user if authenticated, None otherwise.
    
    This dependency is used for endpoints that can work with or without authentication,
    such as viewing articles (where favorited/following status depends on auth).
    Does not raise exceptions for missing or invalid tokens.
    
    Args:
        db: Database session from dependency.
        credentials: HTTP Bearer credentials from Authorization header.
    
    Returns:
        Optional[User]: User object if authenticated and valid, None otherwise.
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    token_data = auth_service.decode_access_token(token)
    
    if token_data is None:
        return None
    
    # Convert token subject (user_id as string) to int
    try:
        user_id = int(token_data.sub)
    except (ValueError, TypeError):
        logger.debug(f"Invalid token subject in optional auth: {token_data.sub}")
        return None
    
    user = await auth_service.get_user_by_id(db, user_id)
    
    if user is None or not user.is_active:
        return None
    
    return user
