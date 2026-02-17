"""Pydantic schemas for authentication requests and responses."""

import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
import bleach


class UserCreate(BaseModel):
    """Schema for user registration.
    
    Validates:
        - Email format and uniqueness (handled in service layer)
        - Username format (alphanumeric, hyphens, underscores, 3-50 chars)
        - Password complexity (uppercase, lowercase, digit, special character, min 8 chars)
    """
    
    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(..., min_length=3, max_length=50, description="User's username")
    password: str = Field(..., min_length=8, max_length=128, description="User's password")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format.
        
        Rules:
            - Must be 3-50 characters
            - Must contain only alphanumeric characters, hyphens, and underscores
            - Cannot start or end with hyphen or underscore
            - No consecutive special characters
            - No reserved system names
        
        Args:
            v: Username to validate
            
        Returns:
            Validated username (lowercase for storage)
            
        Raises:
            ValueError: If username format is invalid
        """
        # Basic character validation
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must contain only alphanumeric characters, hyphens, and underscores')
        
        # Cannot start or end with special characters
        if v[0] in '-_' or v[-1] in '-_':
            raise ValueError('Username cannot start or end with hyphen or underscore')
        
        # No consecutive special characters
        if '--' in v or '__' in v or '-_' in v or '_-' in v:
            raise ValueError('Username cannot contain consecutive special characters')
        
        # Prevent usernames that are too similar to system accounts
        forbidden_usernames = {
            'admin', 'root', 'system', 'api', 'null', 'undefined', 
            'administrator', 'moderator', 'support', 'help', 'user',
            'test', 'demo', 'guest', 'anonymous'
        }
        if v.lower() in forbidden_usernames:
            raise ValueError('This username is reserved and cannot be used')
        
        return v.lower()
    
    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate password complexity.
        
        Password requirements:
            - At least 8 characters (enforced by Field min_length)
            - At least one uppercase letter
            - At least one lowercase letter
            - At least one digit
            - At least one special character
        
        Args:
            v: Password to validate
            
        Returns:
            Validated password
            
        Raises:
            ValueError: If password does not meet complexity requirements
        """
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        # Require at least one special character for stronger passwords
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', v):
            raise ValueError('Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)')
        
        # Check for common weak passwords
        common_passwords = {
            'password', 'password123', '12345678', 'qwerty123', 'abc123456',
            'password1', 'welcome123', 'admin123', 'letmein123', 'passw0rd',
            'password!', 'password1!', 'qwerty12', 'admin1234'
        }
        if v.lower() in common_passwords:
            raise ValueError('This password is too common. Please choose a stronger password')
        
        return v
    
    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalize email to lowercase for consistent storage.
        
        Args:
            v: Email address
            
        Returns:
            Lowercase email address
        """
        return v.lower()
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "user@example.com",
            "username": "johndoe",
            "password": "SecurePass123!"
        }
    })


class UserLogin(BaseModel):
    """Schema for user login.
    
    Validates:
        - Email format
        - Password presence (complexity not checked on login)
    """
    
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=1, max_length=128, description="User's password")
    
    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalize email to lowercase for consistent comparison.
        
        Args:
            v: Email address
            
        Returns:
            Lowercase email address
        """
        return v.lower()
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "user@example.com",
            "password": "SecurePass123!"
        }
    })


class UserUpdate(BaseModel):
    """Schema for updating user information.
    
    All fields are optional. Only provided fields will be updated.
    
    Validates:
        - Email format if provided
        - Username format if provided
        - Password complexity if provided
        - Bio sanitization (XSS prevention)
        - Image URL format if provided (must be HTTP/HTTPS)
    """
    
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Updated username")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Updated password")
    bio: Optional[str] = Field(None, max_length=5000, description="User biography")
    image: Optional[str] = Field(None, max_length=500, description="User profile image URL")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username format if provided.
        
        Args:
            v: Username to validate
            
        Returns:
            Validated username (lowercase) or None
            
        Raises:
            ValueError: If username format is invalid
        """
        if v is None:
            return v
        
        # Basic character validation
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must contain only alphanumeric characters, hyphens, and underscores')
        
        # Cannot start or end with special characters
        if v[0] in '-_' or v[-1] in '-_':
            raise ValueError('Username cannot start or end with hyphen or underscore')
        
        # No consecutive special characters
        if '--' in v or '__' in v or '-_' in v or '_-' in v:
            raise ValueError('Username cannot contain consecutive special characters')
        
        # Prevent usernames that are too similar to system accounts
        forbidden_usernames = {
            'admin', 'root', 'system', 'api', 'null', 'undefined',
            'administrator', 'moderator', 'support', 'help', 'user',
            'test', 'demo', 'guest', 'anonymous'
        }
        if v.lower() in forbidden_usernames:
            raise ValueError('This username is reserved and cannot be used')
        
        return v.lower()
    
    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: Optional[str]) -> Optional[str]:
        """Validate password complexity if provided.
        
        Same requirements as UserCreate password validation.
        
        Args:
            v: Password to validate
            
        Returns:
            Validated password or None
            
        Raises:
            ValueError: If password does not meet complexity requirements
        """
        if v is None:
            return v
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        # Require at least one special character for stronger passwords
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', v):
            raise ValueError('Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)')
        
        # Check for common weak passwords
        common_passwords = {
            'password', 'password123', '12345678', 'qwerty123', 'abc123456',
            'password1', 'welcome123', 'admin123', 'letmein123', 'passw0rd',
            'password!', 'password1!', 'qwerty12', 'admin1234'
        }
        if v.lower() in common_passwords:
            raise ValueError('This password is too common. Please choose a stronger password')
        
        return v
    
    @field_validator('bio')
    @classmethod
    def sanitize_bio(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize bio field to prevent XSS attacks.
        
        Strips all HTML tags and potentially malicious content.
        
        Args:
            v: Bio text to sanitize
            
        Returns:
            Sanitized bio text or None
        """
        if v is None:
            return v
        
        # Strip all HTML tags for security
        sanitized = bleach.clean(v, tags=[], strip=True)
        
        # Trim whitespace
        sanitized = sanitized.strip()
        
        # Return None for empty strings
        return sanitized if sanitized else None
    
    @field_validator('image')
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate image URL format.
        
        Ensures URL starts with http:// or https:// (no data: or javascript: URLs).
        Prevents SSRF and XSS attacks through malicious URLs.
        
        Args:
            v: Image URL to validate
            
        Returns:
            Validated image URL or None
            
        Raises:
            ValueError: If URL format is invalid or uses forbidden scheme
        """
        if v is None:
            return v
        
        # Trim whitespace
        v = v.strip()
        
        # Return None for empty strings
        if not v:
            return None
        
        # Validate URL format - must be HTTP or HTTPS only (prevent data:, javascript:, file:, etc.)
        if not re.match(r'^https?://', v, re.IGNORECASE):
            raise ValueError('Image URL must start with http:// or https://')
        
        # Prevent data: URLs (XSS vector)
        if re.match(r'^data:', v, re.IGNORECASE):
            raise ValueError('Data URLs are not allowed for security reasons')
        
        # Prevent javascript: URLs (XSS vector)
        if 'javascript:' in v.lower():
            raise ValueError('JavaScript URLs are not allowed for security reasons')
        
        # Basic URL structure validation
        if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', v, re.IGNORECASE):
            raise ValueError('Invalid URL format')
        
        # Check URL length
        if len(v) > 500:
            raise ValueError('Image URL is too long (max 500 characters)')
        
        # Prevent localhost/private IPs (SSRF prevention)
        if re.search(r'(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)', v, re.IGNORECASE):
            raise ValueError('URLs pointing to localhost or private networks are not allowed')
        
        return v
    
    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[EmailStr]) -> Optional[str]:
        """Normalize email to lowercase for consistent storage.
        
        Args:
            v: Email address
            
        Returns:
            Lowercase email address or None
        """
        if v is None:
            return v
        return v.lower()
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "newemail@example.com",
            "username": "newusername",
            "bio": "I love coding!",
            "image": "https://example.com/avatar.jpg"
        }
    })


class UserResponse(BaseModel):
    """Schema for user response (matches RealWorld API spec).
    
    Returns user data with JWT token for authenticated requests.
    """
    
    email: str = Field(..., description="User's email address")
    username: str = Field(..., description="User's username")
    bio: Optional[str] = Field(None, description="User biography")
    image: Optional[str] = Field(None, description="User profile image URL")
    token: str = Field(..., description="JWT authentication token")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "username": "johndoe",
                "bio": "I love coding!",
                "image": "https://example.com/avatar.jpg",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )


class UserResponseWrapper(BaseModel):
    """Wrapper for user response to match RealWorld API spec.
    
    The RealWorld API spec requires all user responses to be wrapped
    in a 'user' object.
    """
    
    user: UserResponse
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user": {
                "email": "user@example.com",
                "username": "johndoe",
                "bio": "I love coding!",
                "image": "https://example.com/avatar.jpg",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    })


class UserCreateWrapper(BaseModel):
    """Wrapper for user creation request to match RealWorld API spec.
    
    The RealWorld API spec requires registration data to be wrapped
    in a 'user' object.
    """
    
    user: UserCreate


class UserLoginWrapper(BaseModel):
    """Wrapper for user login request to match RealWorld API spec.
    
    The RealWorld API spec requires login credentials to be wrapped
    in a 'user' object.
    """
    
    user: UserLogin


class UserUpdateWrapper(BaseModel):
    """Wrapper for user update request to match RealWorld API spec.
    
    The RealWorld API spec requires update data to be wrapped
    in a 'user' object.
    """
    
    user: UserUpdate
