from pydantic import BaseModel, ConfigDict, Field


class ProfileBase(BaseModel):
    """Base profile schema with common fields."""
    username: str = Field(..., description="Username of the profile")
    bio: str = Field(default="", description="User biography")
    image: str = Field(default="", description="Profile image URL")
    following: bool = Field(default=False, description="Whether current user follows this profile")

    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(BaseModel):
    """Profile response wrapper matching RealWorld API spec."""
    profile: ProfileBase

    model_config = ConfigDict(from_attributes=True)


class Profile(ProfileBase):
    """Full profile schema."""
    pass
