from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ProfileSchema(BaseModel):
    """Profile schema for API responses."""
    
    username: str = Field(..., description="Username of the profile")
    bio: str = Field(default="", description="User biography")
    image: str = Field(default="", description="Profile image URL")
    following: bool = Field(default=False, description="Whether current user is following this profile")

    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(BaseModel):
    """Wrapper for profile response matching RealWorld API spec."""
    
    profile: ProfileSchema

    model_config = ConfigDict(from_attributes=True)
