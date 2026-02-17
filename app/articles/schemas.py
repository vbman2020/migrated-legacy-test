from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.profiles.schemas import ProfileResponse


class ArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)


class ArticleCreate(ArticleBase):
    tag_list: Optional[List[str]] = Field(default_factory=list, alias="tagList")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

    @field_validator('body')
    @classmethod
    def validate_body(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Body cannot be empty')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Description cannot be empty')
        return v


class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    body: Optional[str] = Field(None, min_length=1)
    tag_list: Optional[List[str]] = Field(default=None, alias="tagList")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError('Title cannot be empty')
        return v.strip() if v else v

    @field_validator('body')
    @classmethod
    def validate_body(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError('Body cannot be empty')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError('Description cannot be empty')
        return v


class ArticleResponse(BaseModel):
    slug: str
    title: str
    description: str
    body: str
    tag_list: List[str] = Field(alias="tagList")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    favorited: bool
    favorites_count: int = Field(alias="favoritesCount")
    author: ProfileResponse

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArticleResponseWrapper(BaseModel):
    article: ArticleResponse


class MultipleArticlesResponse(BaseModel):
    articles: List[ArticleResponse]
    articles_count: int = Field(alias="articlesCount")

    model_config = ConfigDict(populate_by_name=True)


class CommentBase(BaseModel):
    body: str = Field(..., min_length=1)

    @field_validator('body')
    @classmethod
    def validate_body(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Comment body cannot be empty')
        return v


class CommentCreate(CommentBase):
    pass


class CommentResponse(BaseModel):
    id: int
    body: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    author: ProfileResponse

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CommentResponseWrapper(BaseModel):
    comment: CommentResponse


class MultipleCommentsResponse(BaseModel):
    comments: List[CommentResponse]


class TagsResponse(BaseModel):
    tags: List[str]
