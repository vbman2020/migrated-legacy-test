from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Profile schema for author display
class ProfileSchema(BaseModel):
    username: str
    bio: Optional[str] = None
    image: Optional[str] = None
    following: bool = False

    model_config = ConfigDict(from_attributes=True)


# Article Schemas
class ArticleCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=10000)
    body: str = Field(..., min_length=1, max_length=100000)
    tagList: Optional[List[str]] = Field(default_factory=list)

    @field_validator('tagList')
    @classmethod
    def validate_tag_list(cls, v: Optional[List[str]]) -> List[str]:
        if v is None:
            return []
        # Remove duplicates while preserving order, sanitize input
        seen = set()
        unique_tags = []
        for tag in v:
            if not tag or not isinstance(tag, str):
                continue
            # Strip whitespace and limit length
            tag_clean = tag.strip()[:100]
            tag_lower = tag_clean.lower()
            if tag_lower and tag_lower not in seen:
                seen.add(tag_lower)
                unique_tags.append(tag_clean)
        return unique_tags

    model_config = ConfigDict(populate_by_name=True)


class ArticleUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1, max_length=10000)
    body: Optional[str] = Field(None, min_length=1, max_length=100000)
    tagList: Optional[List[str]] = None

    @field_validator('tagList')
    @classmethod
    def validate_tag_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        # Remove duplicates while preserving order, sanitize input
        seen = set()
        unique_tags = []
        for tag in v:
            if not tag or not isinstance(tag, str):
                continue
            # Strip whitespace and limit length
            tag_clean = tag.strip()[:100]
            tag_lower = tag_clean.lower()
            if tag_lower and tag_lower not in seen:
                seen.add(tag_lower)
                unique_tags.append(tag_clean)
        return unique_tags

    model_config = ConfigDict(populate_by_name=True)


class ArticleSchema(BaseModel):
    slug: str
    title: str
    description: str
    body: str
    tagList: List[str] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime
    favorited: bool = False
    favoritesCount: int = 0
    author: ProfileSchema

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArticleResponseSchema(BaseModel):
    article: ArticleSchema


class ArticleListResponseSchema(BaseModel):
    articles: List[ArticleSchema]
    articlesCount: int


# Comment Schemas
class CommentCreateSchema(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class CommentSchema(BaseModel):
    id: int
    createdAt: datetime
    updatedAt: datetime
    body: str
    author: ProfileSchema

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CommentResponseSchema(BaseModel):
    comment: CommentSchema


class CommentListResponseSchema(BaseModel):
    comments: List[CommentSchema]


# Tag Schemas
class TagListResponseSchema(BaseModel):
    tags: List[str]


# Request wrappers for API endpoints
class ArticleCreateRequest(BaseModel):
    article: ArticleCreateSchema


class ArticleUpdateRequest(BaseModel):
    article: ArticleUpdateSchema


class CommentCreateRequest(BaseModel):
    comment: CommentCreateSchema
