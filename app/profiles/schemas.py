from pydantic import BaseModel, ConfigDict, Field


class ProfileResponse(BaseModel):
    """Profile response schema matching the RealWorld API specification."""
    username: str = Field(..., description="Username of the profile")
    bio: str = Field(default="", description="User biography")
    image: str = Field(..., description="Profile image URL")
    following: bool = Field(..., description="Whether the current user is following this profile")

    model_config = ConfigDict(from_attributes=True)


class ProfileResponseWrapper(BaseModel):
    """Wrapper for profile response to match API contract."""
    profile: ProfileResponse

    model_config = ConfigDict(from_attributes=True)
