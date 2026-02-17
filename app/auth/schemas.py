"""Authentication schemas for request/response validation.

All schemas use Pydantic v2 style with ConfigDict and field_validator.
"""

from typing import Optional
import re

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, HttpUrl


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """Schema for user registration.
    
    Password must be 8-128 characters and meet complexity requirements.
    """
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Validate username contains only alphanumeric characters and hyphens.
        
        Underscores are not allowed to prevent homograph attacks.
        """
        if not re.match(r'^[a-zA-Z0-9-]+$', v):
            raise ValueError('Username must contain only alphanumeric characters and hyphens')
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('Username cannot start or end with a hyphen')
        if '--' in v:
            raise ValueError('Username cannot contain consecutive hyphens')
        return v
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password meets complexity requirements.
        
        Requirements:
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserUpdate(BaseModel):
    """Schema for user update.
    
    All fields are optional. Bio and image have validation for length and format.
    """
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    bio: Optional[str] = Field(None, max_length=1000)
    image: Optional[str] = Field(None, max_length=2048)

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: Optional[str]) -> Optional[str]:
        """Validate username contains only alphanumeric characters and hyphens."""
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9-]+$', v):
                raise ValueError('Username must contain only alphanumeric characters and hyphens')
            if v.startswith('-') or v.endswith('-'):
                raise ValueError('Username cannot start or end with a hyphen')
            if '--' in v:
                raise ValueError('Username cannot contain consecutive hyphens')
        return v
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: Optional[str]) -> Optional[str]:
        """Validate password meets complexity requirements if provided."""
        if v is not None:
            if not re.search(r'[A-Z]', v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not re.search(r'[a-z]', v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not re.search(r'\d', v):
                raise ValueError('Password must contain at least one digit')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
                raise ValueError('Password must contain at least one special character')
        return v
    
    @field_validator('image')
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate image is a valid URL if provided."""
        if v is not None and v.strip():
            # Check if it looks like a URL
            if not v.startswith(('http://', 'https://')):
                raise ValueError('Image must be a valid HTTP(S) URL')
            # Basic URL validation
            try:
                # Pydantic's HttpUrl validator
                from pydantic import HttpUrl
                HttpUrl(v)
            except Exception:
                raise ValueError('Image must be a valid URL')
        return v


class UserResponse(BaseModel):
    """Schema for user response."""
    email: EmailStr
    username: str
    bio: Optional[str] = None
    image: Optional[str] = None
    token: str

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserBase):
    """Schema for user in database."""
    id: int
    is_active: bool
    is_staff: bool
    is_superuser: bool
    bio: Optional[str] = None
    image: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Request/Response wrappers for RealWorld API spec
class UserRegistrationRequest(BaseModel):
    """Wrapper for registration request."""
    user: UserCreate


class UserLoginRequest(BaseModel):
    """Wrapper for login request."""
    user: UserLogin


class UserUpdateRequest(BaseModel):
    """Wrapper for update request."""
    user: UserUpdate


class UserResponseWrapper(BaseModel):
    """Wrapper for user response."""
    user: UserResponse
