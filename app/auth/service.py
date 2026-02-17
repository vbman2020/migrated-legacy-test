"""Authentication service with JWT token generation and password management.

Provides secure authentication functionality including:
    - Password hashing with bcrypt
    - JWT token generation and validation
    - User CRUD operations
    - Brute force protection through account locking
    - Comprehensive error logging for security auditing
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.auth.schemas import UserCreate, UserUpdate
from app.config import settings

# Configure logging for security event auditing
logger = logging.getLogger(__name__)

# Password hashing context using bcrypt
# Bcrypt automatically handles salting and timing-safe comparison
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Account lockout configuration
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password asynchronously.
    
    Uses asyncio.to_thread to run CPU-bound bcrypt verification in a thread pool,
    preventing blocking of the async event loop.
    
    Passlib's CryptContext provides timing-safe comparison to prevent timing attacks.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    # Run CPU-bound password verification in thread pool to avoid blocking event loop
    return await asyncio.to_thread(pwd_context.verify, plain_password, hashed_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password (synchronous version).
    
    Passlib's CryptContext provides timing-safe comparison to prevent timing attacks.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    """Hash a password using bcrypt asynchronously.
    
    Uses asyncio.to_thread to run CPU-bound bcrypt hashing in a thread pool,
    preventing blocking of the async event loop.
    
    Bcrypt automatically generates a unique salt for each password.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The hashed password with embedded salt (60 characters)
    """
    # Run CPU-bound password hashing in thread pool to avoid blocking event loop
    return await asyncio.to_thread(pwd_context.hash, password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt (synchronous version).
    
    Bcrypt automatically generates a unique salt for each password.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The hashed password with embedded salt (60 characters)
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.
    
    Encodes user data into a JWT token with configurable expiration.
    Token includes:
        - User ID, email, username (from data dict)
        - Expiration timestamp (exp claim)
        - Issued at timestamp (iat claim)
    
    Args:
        data: Dictionary containing the data to encode in the token
        expires_delta: Optional custom expiration time (defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": now
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode a JWT access token.
    
    Validates token signature, expiration, and structure.
    
    Args:
        token: The JWT token string to decode
        
    Returns:
        Decoded token payload dict if valid, None otherwise
        
    Raises:
        Does not raise exceptions - returns None for any validation failure
        to avoid exposing token validation details
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Validate required claims
        if "id" not in payload:
            logger.warning("Token missing user ID claim")
            return None
        
        # Validate token expiration (jwt.decode already checks exp, but we double-check)
        exp = payload.get("exp")
        if exp is None:
            logger.warning("Token missing expiration claim")
            return None
        
        # Check if token has expired (redundant but explicit)
        if datetime.now(timezone.utc).timestamp() > exp:
            logger.info("Token has expired")
            return None
        
        return payload
    except JWTError as e:
        # Log the error for debugging but don't expose details to client
        logger.warning(f"JWT decode error: {str(e)}")
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error decoding token: {str(e)}")
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get a user by email address.
    
    Email comparison is case-insensitive as emails are stored in lowercase.
    
    Args:
        db: Database session
        email: Email address to search for
        
    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get a user by username.
    
    Username comparison is case-insensitive as usernames are stored in lowercase.
    
    Args:
        db: Database session
        username: Username to search for
        
    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.username == username.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get a user by ID.
    
    Args:
        db: Database session
        user_id: User ID to search for
        
    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def increment_failed_login_attempts(db: AsyncSession, user: User) -> None:
    """Increment failed login attempts and lock account if threshold exceeded.
    
    Implements brute force protection by tracking failed login attempts.
    After MAX_LOGIN_ATTEMPTS, the account is locked for LOCKOUT_DURATION_MINUTES.
    
    Args:
        db: Database session
        user: User object to update
        
    Side Effects:
        - Increments user.failed_login_attempts
        - Sets user.locked_until if threshold exceeded
        - Commits changes to database
    """
    user.failed_login_attempts += 1
    
    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        logger.warning(
            f"User {user.id} locked due to {user.failed_login_attempts} failed login attempts. "
            f"Locked until {user.locked_until}"
        )
    else:
        logger.info(
            f"Failed login attempt {user.failed_login_attempts}/{MAX_LOGIN_ATTEMPTS} for user {user.id}"
        )
    
    await db.commit()
    await db.refresh(user)


async def reset_failed_login_attempts(db: AsyncSession, user: User) -> None:
    """Reset failed login attempts and unlock account.
    
    Called after successful login to reset the brute force protection counters.
    
    Args:
        db: Database session
        user: User object to update
        
    Side Effects:
        - Resets user.failed_login_attempts to 0
        - Clears user.locked_until
        - Commits changes to database
    """
    if user.failed_login_attempts > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()
        await db.refresh(user)
        logger.info(f"Reset failed login attempts for user {user.id}")


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password.
    
    Performs timing-safe password verification to prevent timing attacks.
    Always performs password verification even if user doesn't exist to prevent
    user enumeration through timing analysis.
    
    Implements brute force protection through account locking.
    
    Args:
        db: Database session
        email: User's email address
        password: User's plain text password
        
    Returns:
        User object if authentication successful, None otherwise
        
    Security Notes:
        - Performs constant-time comparison to prevent timing attacks
        - Does not reveal whether email or password was incorrect
        - Implements account lockout after MAX_LOGIN_ATTEMPTS failures
        - Logs failed authentication attempts for security monitoring
    """
    user = await get_user_by_email(db, email)
    
    if not user:
        # Still verify a dummy password to prevent timing attacks
        # This ensures authentication takes similar time whether user exists or not
        await verify_password_async(
            password,
            "$2b$12$dummy.hash.to.prevent.timing.attack.xxxxxxxxxxxxxxxxxxxx"
        )
        logger.info(f"Authentication failed: user not found for email {email}")
        return None
    
    # Check if account is locked
    if user.is_locked():
        logger.warning(f"Authentication failed: user {user.id} account is locked until {user.locked_until}")
        # Still verify password to maintain constant timing
        await verify_password_async(password, user.password)
        return None
    
    # Verify password
    if not await verify_password_async(password, user.password):
        logger.info(f"Authentication failed: invalid password for user {user.id}")
        # Increment failed login attempts
        await increment_failed_login_attempts(db, user)
        return None
    
    # Check if user is active
    if not user.is_active:
        logger.warning(f"Authentication failed: inactive user {user.id}")
        return None
    
    # Successful authentication - reset failed login attempts
    await reset_failed_login_attempts(db, user)
    logger.info(f"User {user.id} authenticated successfully")
    return user


async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    """Create a new user.
    
    Creates user with:
        - Hashed password using bcrypt (60 characters)
        - Normalized (lowercase) email and username for case-insensitive uniqueness
        - Active status by default
        - Empty bio and image (can be updated later)
        - Zero failed login attempts
        - No account lock
    
    Args:
        db: Database session
        user_create: User creation data (validated by Pydantic)
        
    Returns:
        Created User object with all fields populated
        
    Raises:
        IntegrityError: If email or username already exists (caught and re-raised)
        
    Note:
        Caller should handle IntegrityError and provide appropriate user-facing message.
        Email and username are already normalized to lowercase by Pydantic validators.
    """
    # Hash password asynchronously to avoid blocking
    hashed_password = await get_password_hash_async(user_create.password)
    
    # Create user with normalized email and username (already lowercased by Pydantic)
    db_user = User(
        email=user_create.email,
        username=user_create.username,
        password=hashed_password,
        is_active=True,
        bio=None,
        image=None,
        failed_login_attempts=0,
        locked_until=None
    )
    
    try:
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        logger.info(f"Created new user: {db_user.username} (ID: {db_user.id})")
        return db_user
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Failed to create user due to integrity error: {str(e)}")
        # Re-raise to be handled by the router
        raise e


async def update_user(db: AsyncSession, user: User, user_update: UserUpdate) -> User:
    """Update an existing user.
    
    Only updates fields that are provided in user_update (not None).
    Performs validation before update:
        - Email uniqueness (if changing email)
        - Username uniqueness (if changing username)
        - Password hashing (if changing password)
        - Bio sanitization (handled by Pydantic)
        - Image URL validation (handled by Pydantic)
    
    Args:
        db: Database session
        user: User object to update
        user_update: User update data (validated by Pydantic)
        
    Returns:
        Updated User object
        
    Raises:
        IntegrityError: If new email or username already exists
        
    Note:
        Only commits to database if changes were made.
        Caller should handle IntegrityError and provide appropriate user-facing message.
        Email and username are already normalized to lowercase by Pydantic validators.
    """
    # Track if any changes were made
    has_changes = False
    
    # Update email (already normalized to lowercase by Pydantic)
    if user_update.email is not None and user_update.email != user.email:
        user.email = user_update.email
        has_changes = True
        logger.info(f"User {user.id} email updated to {user.email}")
    
    # Update username (already normalized to lowercase by Pydantic)
    if user_update.username is not None and user_update.username != user.username:
        user.username = user_update.username
        has_changes = True
        logger.info(f"User {user.id} username updated to {user.username}")
    
    # Update password (hash asynchronously)
    if user_update.password is not None:
        user.password = await get_password_hash_async(user_update.password)
        has_changes = True
        logger.info(f"User {user.id} password updated")
    
    # Update bio (sanitized by Pydantic validator)
    if user_update.bio is not None:
        user.bio = user_update.bio
        has_changes = True
        logger.info(f"User {user.id} bio updated")
    
    # Update image (validated by Pydantic validator)
    if user_update.image is not None:
        user.image = user_update.image
        has_changes = True
        logger.info(f"User {user.id} image updated")
    
    # Only commit if there were actual changes
    if has_changes:
        try:
            await db.commit()
            await db.refresh(user)
            logger.info(f"User {user.id} successfully updated")
        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"Failed to update user {user.id} due to integrity error: {str(e)}")
            raise e
    else:
        logger.info(f"No changes to update for user {user.id}")
    
    return user


def generate_token_for_user(user: User) -> str:
    """Generate a JWT token for a user.
    
    Creates a token containing user identification data.
    Token expires after settings.ACCESS_TOKEN_EXPIRE_MINUTES (default 60 minutes).
    
    Args:
        user: User object to generate token for
        
    Returns:
        JWT token string containing user id, email, and username
        
    Note:
        Token expiration is validated during decode_access_token.
    """
    token_data = {
        "id": user.id,
        "email": user.email,
        "username": user.username
    }
    return create_access_token(token_data)


async def check_user_exists(db: AsyncSession, email: Optional[str] = None, username: Optional[str] = None) -> bool:
    """Check if a user exists with the given email or username.
    
    Performs case-insensitive search as emails and usernames are stored in lowercase.
    
    Args:
        db: Database session
        email: Email to check (optional)
        username: Username to check (optional)
        
    Returns:
        True if user exists with matching email or username, False otherwise
        
    Note:
        At least one of email or username should be provided.
        If both provided, returns True if either matches.
    """
    conditions = []
    if email:
        conditions.append(User.email == email.lower())
    if username:
        conditions.append(User.username == username.lower())
    
    if not conditions:
        return False
    
    result = await db.execute(
        select(User).where(or_(*conditions))
    )
    return result.scalar_one_or_none() is not None
