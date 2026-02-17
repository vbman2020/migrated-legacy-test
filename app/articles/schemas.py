from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Maximum lengths for validation
MAX_ARTICLE_BODY_LENGTH = 500000  # 500KB text limit
MAX_COMMENT_BODY_LENGTH = 50000   # 50KB text limit
MAX_TAG_LENGTH = 255
MAX_TITLE_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 5000
MAX_TAGS_PER_ARTICLE = 20  # Reduced from 50 to prevent resource exhaustion


class ProfileSchema(BaseModel):
    """Embedded profile schema for article/comment author."""
    username: str
    bio: Optional[str] = None
    image: Optional[str] = None
    following: bool = False

    model_config = ConfigDict(from_attributes=True)


class ArticleBase(BaseModel):
    title: str = Field(..., max_length=MAX_TITLE_LENGTH)
    description: str = Field(..., max_length=MAX_DESCRIPTION_LENGTH)
    body: str = Field(..., max_length=MAX_ARTICLE_BODY_LENGTH)


class ArticleCreate(ArticleBase):
    tagList: Optional[List[str]] = Field(default_factory=list)

    @field_validator('tagList')
    @classmethod
    def validate_tag_list(cls, v: Optional[List[str]]) -> List[str]:
        if v is None:
            return []
        
        # Check maximum number of tags
        if len(v) > MAX_TAGS_PER_ARTICLE:
            raise ValueError(f"Maximum {MAX_TAGS_PER_ARTICLE} tags allowed per article")
        
        # Filter out empty strings, strip whitespace, and validate length
        validated_tags = []
        seen_tags = set()
        
        for tag in v:
            if tag and tag.strip():
                cleaned_tag = tag.strip()
                
                # Prevent duplicates (case-insensitive)
                if cleaned_tag.lower() in seen_tags:
                    continue
                seen_tags.add(cleaned_tag.lower())
                
                if len(cleaned_tag) > MAX_TAG_LENGTH:
                    raise ValueError(f"Tag '{cleaned_tag}' exceeds maximum length of {MAX_TAG_LENGTH}")
                validated_tags.append(cleaned_tag)
        
        return validated_tags

    model_config = ConfigDict(populate_by_name=True)


class ArticleCreateWrapper(BaseModel):
    """Wrapper for nested article creation."""
    article: ArticleCreate


class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=MAX_TITLE_LENGTH)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    body: Optional[str] = Field(None, max_length=MAX_ARTICLE_BODY_LENGTH)

    model_config = ConfigDict(populate_by_name=True)


class ArticleUpdateWrapper(BaseModel):
    """Wrapper for nested article update."""
    article: ArticleUpdate


class ArticleResponse(ArticleBase):
    slug: str
    tagList: List[str] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime
    favorited: bool = False
    favoritesCount: int = 0
    author: ProfileSchema

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArticleResponseWrapper(BaseModel):
    article: ArticleResponse


class ArticleListResponse(BaseModel):
    articles: List[ArticleResponse]
    articlesCount: int


class CommentBase(BaseModel):
    body: str = Field(..., max_length=MAX_COMMENT_BODY_LENGTH)


class CommentCreate(CommentBase):
    pass


class CommentCreateWrapper(BaseModel):
    """Wrapper for nested comment creation."""
    comment: CommentCreate


class CommentResponse(CommentBase):
    id: int
    createdAt: datetime
    updatedAt: datetime
    author: ProfileSchema

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CommentResponseWrapper(BaseModel):
    comment: CommentResponse


class CommentListResponse(BaseModel):
    comments: List[CommentResponse]


class TagsResponse(BaseModel):
    tags: List[str]
