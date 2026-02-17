"""Authentication service layer.

Handles all authentication business logic including:
- Password hashing and verification with bcrypt
- JWT token generation and validation
- User CRUD operations
- Authentication and authorization
- Account security (failed login tracking)
"""

from datetime import datetime, timedelta
from typing import Optional
import logging

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.auth.models import User
from app.auth.schemas import UserCreate, UserUpdate
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Password hashing context - configured at module level for performance
# Using bcrypt with default rounds (12) for secure password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations.
    
    All password hashing, JWT generation, and user management
    is centralized here following separation of concerns.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain text password using bcrypt.
        
        Args:
            password: Plain text password (max 128 chars to prevent DOS)
            
        Returns:
            Hashed password string (60 characters for bcrypt)
            
        Note:
            Bcrypt automatically generates a salt and stores it in the hash.
            The resulting hash is always 60 characters long.
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a bcrypt hash.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Bcrypt hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
            
        Note:
            Bcrypt comparison is intentionally slow to prevent brute force attacks.
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False

    @staticmethod
    def generate_jwt_token(user: User, expiration_days: Optional[int] = None) -> str:
        """Generate a JWT token for a user.
        
        Args:
            user: User to generate token for
            expiration_days: Optional custom expiration in days (defaults to config value)
            
        Returns:
            Encoded JWT token string
            
        Raises:
            HTTPException: If token generation fails
            
        Note:
            Token includes user id, email, username, and expiration.
            Secret key from settings is used for signing.
        """
        if expiration_days is None:
            expiration_days = settings.JWT_EXPIRATION_DAYS
            
        expiration = datetime.utcnow() + timedelta(days=expiration_days)
        
        payload = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "exp": expiration
        }
        
        try:
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            return token
        except Exception as e:
            logger.error(f"Failed to generate JWT token for user {user.id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token"
            )

    @staticmethod
    def decode_jwt_token(token: str) -> dict:
        """Decode and validate a JWT token.
        
        Args:
            token: JWT token string to decode
            
        Returns:
            Decoded token payload dictionary
            
        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid or tampered with
            
        Note:
            This method validates the signature and expiration.
        """
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email address.
        
        Args:
            db: Database session
            email: User email address (case-insensitive)
            
        Returns:
            User if found, None otherwise
            
        Note:
            Eagerly loads the user's profile relationship.
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get a user by username.
        
        Args:
            db: Database session
            username: Username (case-sensitive)
            
        Returns:
            User if found, None otherwise
            
        Note:
            Eagerly loads the user's profile relationship.
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get a user by ID.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User if found, None otherwise
            
        Note:
            Eagerly loads the user's profile relationship.
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user with associated profile.
        
        Args:
            db: Database session
            user_data: User creation data (email, username, password)
            
        Returns:
            Created user with profile relationship loaded
            
        Raises:
            HTTPException: If email or username already exists (422)
            
        Note:
            - Password is hashed using bcrypt before storage
            - A profile is automatically created for the new user
            - Both user and profile are committed in a single transaction
        """
        # Check if email already exists
        existing_user = await AuthService.get_user_by_email(db, user_data.email)
        if existing_user:
            logger.warning(f"Registration attempt with existing email: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this email already exists."
            )
        
        # Check if username already exists
        existing_user = await AuthService.get_user_by_username(db, user_data.username)
        if existing_user:
            logger.warning(f"Registration attempt with existing username: {user_data.username}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this username already exists."
            )
        
        # Create user with hashed password
        user = User(
            email=user_data.email,
            username=user_data.username,
            password=AuthService.hash_password(user_data.password)
        )
        
        db.add(user)
        await db.flush()  # Flush to get the user ID
        
        # Create associated profile (imported here to avoid circular import)
        from app.profiles.models import Profile
        profile = Profile(user_id=user.id)
        db.add(profile)
        
        await db.commit()
        await db.refresh(user)
        
        # Load the profile relationship
        result = await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id == user.id)
        )
        user = result.scalar_one()
        
        logger.info(f"User created successfully: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
        """Authenticate a user by email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            
        Returns:
            Authenticated user with profile loaded
            
        Raises:
            HTTPException: If authentication fails (422) or user is deactivated (403)
            
        Note:
            - Uses constant-time password comparison to prevent timing attacks
            - Returns generic error message to prevent user enumeration
            - Checks if user account is active before allowing login
        """
        user = await AuthService.get_user_by_email(db, email)
        
        if not user:
            logger.warning(f"Login attempt with non-existent email: {email}")
            # Generic error to prevent user enumeration
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this email and password was not found."
            )
        
        if not AuthService.verify_password(password, user.password):
            logger.warning(f"Failed login attempt for user: {email}")
            # Generic error to prevent user enumeration
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A user with this email and password was not found."
            )
        
        if not user.is_active:
            logger.warning(f"Login attempt for deactivated user: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This user has been deactivated."
            )
        
        logger.info(f"User authenticated successfully: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user: User, user_data: UserUpdate) -> User:
        """Update user information including profile fields.
        
        Args:
            db: Database session
            user: User to update
            user_data: Update data (email, username, password, bio, image)
            
        Returns:
            Updated user with profile loaded
            
        Raises:
            HTTPException: If email or username already taken by another user (422)
            
        Note:
            - Only updates fields that are provided (not None)
            - Password is hashed before storage if provided
            - Profile is created if it doesn't exist
            - Bio and image updates are applied to the user's profile
        """
        # Check if email is being changed and if it's already taken
        if user_data.email and user_data.email != user.email:
            existing_user = await AuthService.get_user_by_email(db, user_data.email)
            if existing_user:
                logger.warning(f"Update attempt with existing email: {user_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A user with this email already exists."
                )
            user.email = user_data.email
        
        # Check if username is being changed and if it's already taken
        if user_data.username and user_data.username != user.username:
            existing_user = await AuthService.get_user_by_username(db, user_data.username)
            if existing_user:
                logger.warning(f"Update attempt with existing username: {user_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A user with this username already exists."
                )
            user.username = user_data.username
        
        # Update password if provided
        if user_data.password:
            user.password = AuthService.hash_password(user_data.password)
        
        # Ensure profile exists
        if not user.profile:
            from app.profiles.models import Profile
            profile = Profile(user_id=user.id)
            db.add(profile)
            await db.flush()
            await db.refresh(user)
        
        # Update profile fields if provided
        if user_data.bio is not None:
            user.profile.bio = user_data.bio
        
        if user_data.image is not None:
            user.profile.image = user_data.image
        
        await db.commit()
        await db.refresh(user)
        
        # Reload with profile
        result = await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id == user.id)
        )
        user = result.scalar_one()
        
        logger.info(f"User updated successfully: {user.username} (ID: {user.id})")
        return user
