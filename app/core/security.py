"""Security utilities for JWT token generation/validation and password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt, ExpiredSignatureError
from passlib.context import CryptContext

from app.config import settings


# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to verify against
        
    Returns:
        True if password matches, False otherwise
    """
    if not plain_password or not hashed_password:
        return False
    
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a plain password using bcrypt.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The hashed password string
        
    Raises:
        ValueError: If password is empty or None
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    return pwd_context.hash(password)


def create_access_token(user_id: int) -> str:
    """Generate a JWT token for a user.
    
    Args:
        user_id: The ID of the user to create a token for
        
    Returns:
        The encoded JWT token string
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRATION_DAYS)
    
    to_encode = {
        "id": user_id,
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[int]:
    """Decode a JWT token and extract the user ID.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        The user ID from the token, or None if invalid/expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: int = payload.get("id")
        return user_id
    except ExpiredSignatureError:
        # Token has expired
        return None
    except JWTError:
        # Invalid token signature or malformed token
        return None
    except Exception:
        # Any other error
        return None
