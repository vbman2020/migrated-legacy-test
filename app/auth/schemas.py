"""Pydantic schemas for authentication requests and responses."""
import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class UserRegistration(BaseModel):
    """Schema for user registration request."""
    username: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username doesn't contain invalid characters."""
        if not v.strip():
            raise ValueError('Username cannot be empty or only whitespace')
        # Allow alphanumeric, underscore, and hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity - requires letters, numbers, and special characters."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be at most 128 characters long')
        
        # Require at least one lowercase letter
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        # Require at least one uppercase letter
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        # Require at least one number
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        
        # Require at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        
        return v


class UserRegistrationRequest(BaseModel):
    """Wrapper schema for registration request."""
    user: UserRegistration


class UserLogin(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserLoginRequest(BaseModel):
    """Wrapper schema for login request."""
    user: UserLogin


class UserUpdate(BaseModel):
    """Schema for user update request."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    bio: Optional[str] = None
    image: Optional[str] = None

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username doesn't contain invalid characters."""
        if v is None:
            return v
        if not v.strip():
            raise ValueError('Username cannot be empty or only whitespace')
        # Allow alphanumeric, underscore, and hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Validate password complexity - requires letters, numbers, and special characters."""
        if v is None:
            return v
        
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be at most 128 characters long')
        
        # Require at least one lowercase letter
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        # Require at least one uppercase letter
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        # Require at least one number
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        
        # Require at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        
        return v


class UserUpdateRequest(BaseModel):
    """Wrapper schema for user update request."""
    user: UserUpdate


class UserResponse(BaseModel):
    """Schema for user response."""
    email: str
    username: str
    bio: Optional[str] = None
    image: Optional[str] = None
    token: str

    model_config = ConfigDict(from_attributes=True)


class UserResponseWrapper(BaseModel):
    """Wrapper schema for user response."""
    user: UserResponse


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: str  # user id as string (consistent with JWT encoding)
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp

    model_config = ConfigDict(from_attributes=True)
