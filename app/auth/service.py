"""Business logic for authentication operations."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.auth.schemas import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password, decode_access_token


class AuthService:
    """Service class for authentication business logic.
    
    Handles all user-related operations including:
    - User creation and retrieval
    - Authentication and password verification
    - User updates
    - Token validation
    """
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email address.
        
        Args:
            db: Database session
            email: Email address to search for
            
        Returns:
            User object if found, None otherwise
        """
        stmt = select(User).where(User.email == email).options(selectinload(User.profile))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get a user by username.
        
        Args:
            db: Database session
            username: Username to search for
            
        Returns:
            User object if found, None otherwise
        """
        stmt = select(User).where(User.username == username).options(selectinload(User.profile))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get a user by ID.
        
        Args:
            db: Database session
            user_id: User ID to search for
            
        Returns:
            User object if found, None otherwise
        """
        stmt = select(User).where(User.id == user_id).options(selectinload(User.profile))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
        """Create a new user with hashed password.
        
        The user's profile will be created automatically via the Profile model's
        event listener (see app/profiles/models.py).
        
        Args:
            db: Database session
            user_create: User creation data with email, username, and plain password
            
        Returns:
            Created User object with profile relationship loaded
        """
        # Hash the password using security utilities
        password_hash = get_password_hash(user_create.password)
        
        # Create the user with hashed password
        user = User(
            email=user_create.email,
            username=user_create.username,
            password_hash=password_hash
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Load the profile relationship (created by signal/event)
        await db.refresh(user, ["profile"])
        
        return user
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """Authenticate a user with email and password.
        
        Performs the following checks:
        1. User exists with given email
        2. Password matches stored hash
        3. User account is active
        
        Args:
            db: Database session
            email: User's email
            password: Plain text password to verify
            
        Returns:
            User object if authentication successful, None otherwise
        """
        user = await AuthService.get_user_by_email(db, email)
        
        if not user:
            return None
        
        # Verify password using security utilities
        if not verify_password(password, user.password_hash):
            return None
        
        # Check if user account is active
        if not user.is_active:
            return None
        
        return user
    
    @staticmethod
    async def update_user(
        db: AsyncSession,
        user: User,
        user_update: UserUpdate
    ) -> User:
        """Update user information including profile fields.
        
        Only updates fields that are provided (not None) in user_update.
        Password is hashed before storage.
        
        Args:
            db: Database session
            user: User object to update
            user_update: Update data with optional fields
            
        Returns:
            Updated User object with refreshed relationships
        """
        # Update user fields if provided
        if user_update.email is not None:
            user.email = user_update.email
        
        if user_update.username is not None:
            user.username = user_update.username
        
        if user_update.password is not None:
            # Hash the new password
            user.password_hash = get_password_hash(user_update.password)
        
        # Update profile fields if provided and profile exists
        if user.profile:
            if user_update.bio is not None:
                user.profile.bio = user_update.bio
            
            if user_update.image is not None:
                user.profile.image = user_update.image
        
        await db.commit()
        await db.refresh(user)
        await db.refresh(user, ["profile"])
        
        return user
    
    @staticmethod
    async def get_current_user_from_token(
        db: AsyncSession,
        token: str
    ) -> Optional[User]:
        """Get the current user from a JWT token.
        
        Validates the token and retrieves the associated user.
        
        Args:
            db: Database session
            token: JWT token string
            
        Returns:
            User object if token is valid and user exists, None otherwise
        """
        user_id = decode_access_token(token)
        
        if user_id is None:
            return None
        
        return await AuthService.get_user_by_id(db, user_id)
