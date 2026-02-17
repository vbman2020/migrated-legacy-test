"""Pydantic schemas for articles, comments, and tags."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.profiles.schemas import ProfileResponse


class TagSchema(BaseModel):
    """Tag schema."""

    tag: str

    model_config = ConfigDict(from_attributes=True)


class TagListResponse(BaseModel):
    """Response schema for tag list."""

    tags: List[str]


class ArticleBase(BaseModel):
    """Base article schema with common fields."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1, max_length=100000)

    @field_validator('title', 'description', 'body')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that strings are not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty or whitespace only')
        return v.strip()


class ArticleCreate(ArticleBase):
    """Schema for creating an article."""

    tagList: Optional[List[str]] = Field(default_factory=list)

    @field_validator('tagList')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> List[str]:
        """Validate and sanitize tags."""
        if not v:
            return []
        # Remove empty strings and duplicates, strip whitespace
        sanitized = []
        seen = set()
        for tag in v:
            if tag and isinstance(tag, str):
                cleaned = tag.strip()[:255]  # Limit tag length
                if cleaned and cleaned.lower() not in seen:
                    sanitized.append(cleaned)
                    seen.add(cleaned.lower())
        return sanitized


class ArticleUpdate(BaseModel):
    """Schema for updating an article."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    body: Optional[str] = Field(None, min_length=1, max_length=100000)
    tagList: Optional[List[str]] = None

    @field_validator('title', 'description', 'body')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that strings are not empty or just whitespace."""
        if v is not None:
            if not v.strip():
                raise ValueError('Field cannot be empty or whitespace only')
            return v.strip()
        return v

    @field_validator('tagList')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and sanitize tags."""
        if v is None:
            return None
        # Remove empty strings and duplicates, strip whitespace
        sanitized = []
        seen = set()
        for tag in v:
            if tag and isinstance(tag, str):
                cleaned = tag.strip()[:255]  # Limit tag length
                if cleaned and cleaned.lower() not in seen:
                    sanitized.append(cleaned)
                    seen.add(cleaned.lower())
        return sanitized


class ArticleResponse(BaseModel):
    """Response schema for a single article."""

    slug: str
    title: str
    description: str
    body: str
    tagList: List[str]
    createdAt: datetime
    updatedAt: datetime
    favorited: bool
    favoritesCount: int
    author: ProfileResponse

    model_config = ConfigDict(from_attributes=True)


class ArticleCreateRequest(BaseModel):
    """Wrapper for article creation request."""

    article: ArticleCreate


class ArticleUpdateRequest(BaseModel):
    """Wrapper for article update request."""

    article: ArticleUpdate


class ArticleResponseWrapper(BaseModel):
    """Wrapper for single article response."""

    article: ArticleResponse


class ArticleListResponse(BaseModel):
    """Response schema for article list."""

    articles: List[ArticleResponse]
    articlesCount: int


class CommentBase(BaseModel):
    """Base comment schema."""

    body: str = Field(..., min_length=1, max_length=10000)

    @field_validator('body')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that body is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError('Comment body cannot be empty or whitespace only')
        return v.strip()


class CommentCreate(CommentBase):
    """Schema for creating a comment."""

    pass


class CommentResponse(BaseModel):
    """Response schema for a single comment."""

    id: int
    createdAt: datetime
    updatedAt: datetime
    body: str
    author: ProfileResponse

    model_config = ConfigDict(from_attributes=True)


class CommentCreateRequest(BaseModel):
    """Wrapper for comment creation request."""

    comment: CommentCreate


class CommentResponseWrapper(BaseModel):
    """Wrapper for single comment response."""

    comment: CommentResponse


class CommentListResponse(BaseModel):
    """Response schema for comment list."""

    comments: List[CommentResponse]
