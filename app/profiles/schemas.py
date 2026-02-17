"""Profile Pydantic schemas.

Defines the response schemas for profile endpoints following the RealWorld API spec.
"""

from pydantic import BaseModel, ConfigDict, Field


class ProfileResponse(BaseModel):
    """Profile response schema matching RealWorld API spec.
    
    Attributes:
        username: The user's unique username
        bio: User's biography (empty string if not set)
        image: URL to user's profile image (default placeholder if not set)
        following: Whether the current user is following this profile
    """
    username: str
    bio: str = ""
    image: str = "https://static.productionready.io/images/smiley-cyrus.jpg"
    following: bool = False

    model_config = ConfigDict(from_attributes=True)


class ProfileResponseWrapper(BaseModel):
    """Wrapper for profile response to match RealWorld API spec.
    
    The RealWorld API wraps profile responses in a 'profile' key.
    """
    profile: ProfileResponse

    model_config = ConfigDict(from_attributes=True)
