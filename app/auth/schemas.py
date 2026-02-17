"""Pydantic schemas for authentication endpoints."""

from typing import Optional
import re

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class UserBase(BaseModel):
    """Base schema for User with common fields."""
    
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=255)


class UserCreate(BaseModel):
    """Schema for user registration.
    
    Validates:
    - Email format
    - Username length and characters
    - Password strength (min 8 chars, contains letter and number)
    """
    
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username contains only allowed characters."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                'Username must contain only alphanumeric characters, hyphens, and underscores'
            )
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets strength requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one letter
        - At least one number
        
        Args:
            v: Password string to validate
            
        Returns:
            The validated password string
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_letter = any(c.isalpha() for c in v)
        has_number = any(c.isdigit() for c in v)
        
        if not (has_letter and has_number):
            raise ValueError(
                'Password must contain at least one letter and one number'
            )
        
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v: EmailStr) -> EmailStr:
        """Additional email validation beyond EmailStr."""
        email_str = str(v)
        # Check for valid email format with proper domain
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_str):
            raise ValueError('Invalid email format')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Schema for updating user information.
    
    All fields are optional. Only provided fields will be updated.
    Password is write-only and will be hashed before storage.
    """
    
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    bio: Optional[str] = None
    image: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username contains only allowed characters."""
        if v is not None and not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                'Username must contain only alphanumeric characters, hyphens, and underscores'
            )
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: Optional[str]) -> Optional[str]:
        """Validate password meets strength requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one letter
        - At least one number
        
        Args:
            v: Password string to validate (optional)
            
        Returns:
            The validated password string or None
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        if v is None:
            return v
        
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_letter = any(c.isalpha() for c in v)
        has_number = any(c.isdigit() for c in v)
        
        if not (has_letter and has_number):
            raise ValueError(
                'Password must contain at least one letter and one number'
            )
        
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v: Optional[EmailStr]) -> Optional[EmailStr]:
        """Additional email validation beyond EmailStr."""
        if v is None:
            return v
        
        email_str = str(v)
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_str):
            raise ValueError('Invalid email format')
        return v


class UserResponse(BaseModel):
    """Schema for user response with profile data.
    
    This schema never exposes sensitive fields like password_hash.
    Token is included for authentication.
    """
    
    email: EmailStr
    username: str
    bio: Optional[str] = None
    image: Optional[str] = None
    token: str
    
    model_config = ConfigDict(from_attributes=True)


class UserInDB(BaseModel):
    """Schema representing a user in the database.
    
    Used internally, does not expose password_hash.
    """
    
    id: int
    email: EmailStr
    username: str
    is_active: bool
    is_staff: bool
    is_superuser: bool
    
    model_config = ConfigDict(from_attributes=True)


class UserRegistrationRequest(BaseModel):
    """Wrapper for registration request matching API spec.
    
    API expects: {"user": {"email": "...", "username": "...", "password": "..."}}
    """
    
    user: UserCreate


class UserLoginRequest(BaseModel):
    """Wrapper for login request matching API spec.
    
    API expects: {"user": {"email": "...", "password": "..."}}
    """
    
    user: UserLogin


class UserUpdateRequest(BaseModel):
    """Wrapper for update request matching API spec.
    
    API expects: {"user": {"email": "...", ...}}
    All fields in the nested user object are optional.
    """
    
    user: UserUpdate


class UserResponseWrapper(BaseModel):
    """Wrapper for user response matching API spec.
    
    API returns: {"user": {"email": "...", "token": "...", ...}}
    """
    
    user: UserResponse
