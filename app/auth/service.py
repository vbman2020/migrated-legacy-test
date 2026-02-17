"""Business logic for authentication operations."""
import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.auth.schemas import TokenPayload
from app.config import settings


# Configure logging for security events
logger = logging.getLogger(__name__)

# Password hashing context with strong bcrypt settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Explicit rounds for consistent security
)

# Token expiration settings (short-lived tokens for better security)
DEFAULT_TOKEN_EXPIRATION_MINUTES = 60  # 1 hour
MAX_TOKEN_EXPIRATION_DAYS = 7  # Maximum 7 days


class AuthService:
    """Service class for authentication operations.
    
    Handles user authentication, registration, token management,
    and password operations with security logging.
    """

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash.
        
        Args:
            plain_password: Plain text password to verify.
            hashed_password: Hashed password to compare against.
            
        Returns:
            bool: True if password matches, False otherwise.
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt with strong settings.
        
        Args:
            password: Plain text password to hash.
            
        Returns:
            str: Hashed password.
            
        Raises:
            ValueError: If password is empty or invalid.
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        if len(password) > 128:
            raise ValueError("Password too long (max 128 characters)")
        
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        user_id: int,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token with configurable expiration.
        
        Args:
            user_id: ID of the user to create token for.
            expires_delta: Optional custom expiration time delta.
            
        Returns:
            str: Encoded JWT token.
            
        Raises:
            ValueError: If JWT_SECRET_KEY is not configured.
        """
        # Validate secret key is set
        if not settings.JWT_SECRET_KEY or settings.JWT_SECRET_KEY == "your-secret-key-here":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong secret value. "
                "Do not use default or weak keys in production."
            )
        
        now = datetime.utcnow()
        
        if expires_delta:
            # Enforce maximum expiration limit for security
            max_delta = timedelta(days=MAX_TOKEN_EXPIRATION_DAYS)
            if expires_delta > max_delta:
                logger.warning(
                    f"Token expiration {expires_delta} exceeds maximum {max_delta}, using maximum"
                )
                expires_delta = max_delta
            expire = now + expires_delta
        else:
            # Use configured expiration or default to 1 hour
            expiration_minutes = getattr(
                settings,
                'JWT_EXPIRATION_MINUTES',
                DEFAULT_TOKEN_EXPIRATION_MINUTES
            )
            expire = now + timedelta(minutes=expiration_minutes)

        payload = {
            "sub": str(user_id),  # Store as string for JWT compatibility
            "exp": expire,
            "iat": now
        }

        try:
            encoded_jwt = jwt.encode(
                payload,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM
            )
            return encoded_jwt
        except Exception as e:
            logger.error(f"Token creation error: {str(e)}")
            raise ValueError(f"Failed to create access token: {str(e)}")

    @staticmethod
    def decode_access_token(token: str) -> Optional[TokenPayload]:
        """Decode and validate a JWT access token.
        
        Args:
            token: JWT token string to decode.
            
        Returns:
            Optional[TokenPayload]: Decoded token payload if valid, None otherwise.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            sub = payload.get("sub")
            exp = payload.get("exp")
            iat = payload.get("iat")
            
            if not sub or not exp or not iat:
                logger.warning("Token missing required fields")
                return None
            
            token_data = TokenPayload(
                sub=str(sub),
                exp=int(exp),
                iat=int(iat)
            )
            return token_data
        except jwt.ExpiredSignatureError:
            logger.debug("Token has expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"Token payload error: {str(e)}")
            return None

    @staticmethod
    async def get_user_by_email(
        db: AsyncSession,
        email: str
    ):
        """Get a user by email address.
        
        Args:
            db: Database session.
            email: Email address to search for.
            
        Returns:
            Optional[User]: User object if found, None otherwise.
        """
        from app.auth.models import User
        
        try:
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(f"Error fetching user by email: {str(e)}")
            return None

    @staticmethod
    async def get_user_by_username(
        db: AsyncSession,
        username: str
    ):
        """Get a user by username.
        
        Args:
            db: Database session.
            username: Username to search for.
            
        Returns:
            Optional[User]: User object if found, None otherwise.
        """
        from app.auth.models import User
        
        try:
            stmt = select(User).where(User.username == username)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(f"Error fetching user by username: {str(e)}")
            return None

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: int
    ):
        """Get a user by ID.
        
        Args:
            db: Database session.
            user_id: User ID to search for.
            
        Returns:
            Optional[User]: User object if found, None otherwise.
        """
        from app.auth.models import User
        
        try:
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(f"Error fetching user by ID: {str(e)}")
            return None

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ):
        """Authenticate a user with email and password.
        
        Uses constant-time comparisons to prevent timing attacks.
        Logs failed authentication attempts for security monitoring.
        
        Args:
            db: Database session.
            email: User's email address.
            password: User's plain text password.
            
        Returns:
            Optional[User]: User object if authentication succeeds, None otherwise.
        """
        user = await AuthService.get_user_by_email(db, email)
        
        # Always verify a password to prevent timing attacks that could reveal valid emails
        if not user:
            # Verify against a dummy hash to maintain constant time
            AuthService.verify_password(
                password,
                "$2b$12$dummyhashtopreventtimingattacksdummyhashtopreventtimingattacks"
            )
            logger.warning(f"Failed login attempt for non-existent email: {email}")
            return None
        
        # Verify password
        if not AuthService.verify_password(password, user.password_hash):
            logger.warning(f"Failed login attempt for user: {email} (invalid password)")
            return None
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt for inactive account: {email}")
            return None
        
        logger.info(f"Successful login for user: {email}")
        return user

    @staticmethod
    async def create_user(
        db: AsyncSession,
        username: str,
        email: str,
        password: str
    ):
        """Create a new user with associated profile.
        
        This mimics the Django signal behavior that automatically creates
        a profile when a user is created.
        
        Args:
            db: Database session.
            username: Unique username for the user.
            email: Unique email address for the user.
            password: Plain text password (will be hashed).
            
        Returns:
            User: Created user object with profile.
            
        Raises:
            IntegrityError: If username or email already exists.
            ValueError: If password is invalid.
        """
        from app.auth.models import User
        from app.profiles.models import Profile
        
        try:
            # Hash the password
            hashed_password = AuthService.hash_password(password)
            
            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=hashed_password,
                is_active=True,
                is_staff=False
            )
            
            db.add(user)
            await db.flush()  # Flush to get the user ID
            
            # Create associated profile (mimics Django signal behavior)
            profile = Profile(
                user_id=user.id,
                bio="",
                image=None
            )
            db.add(profile)
            
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"New user registered: {email}")
            return user
            
        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"Failed to create user (duplicate): {email}")
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        bio: Optional[str] = None,
        image: Optional[str] = None
    ):
        """Update user information including profile fields.
        
        Args:
            db: Database session.
            user: User object to update.
            email: New email address (optional).
            username: New username (optional).
            password: New password - will be hashed (optional).
            bio: New bio text (optional).
            image: New image URL (optional).
            
        Returns:
            User: Updated user object.
            
        Raises:
            IntegrityError: If email or username conflicts with existing user.
        """
        try:
            # Update user fields
            if email is not None:
                user.email = email
            
            if username is not None:
                user.username = username
            
            if password is not None:
                user.password_hash = AuthService.hash_password(password)
            
            # Update profile fields if provided and profile exists
            if hasattr(user, 'profile') and user.profile:
                if bio is not None:
                    user.profile.bio = bio
                
                if image is not None:
                    user.profile.image = image
            
            user.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"User updated: {user.email}")
            return user
            
        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"Failed to update user (duplicate): {user.email}")
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating user: {str(e)}")
            raise


# Singleton instance for dependency injection
auth_service = AuthService()
