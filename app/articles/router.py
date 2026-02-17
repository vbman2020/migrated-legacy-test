from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.models import User
from app.database import get_db

from .schemas import (
    ArticleCreateRequest,
    ArticleListResponseSchema,
    ArticleResponseSchema,
    ArticleUpdateRequest,
    CommentCreateRequest,
    CommentListResponseSchema,
    CommentResponseSchema,
    TagListResponseSchema,
)
from .service import ArticleService, CommentService, TagService

router = APIRouter()


@router.get("/articles", response_model=ArticleListResponseSchema, tags=["Articles"])
async def list_articles(
    tag: Optional[str] = Query(None, max_length=100),
    author: Optional[str] = Query(None, max_length=100),
    favorited: Optional[str] = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of articles with optional filtering.
    
    Query params:
    - tag: Filter by tag name
    - author: Filter by author username
    - favorited: Filter by username who favorited
    - limit: Number of articles to return (default 20, max 100)
    - offset: Number of articles to skip (default 0)
    """
    service = ArticleService(db)
    articles, total_count = await service.list_articles(
        tag=tag,
        author=author,
        favorited=favorited,
        limit=limit,
        offset=offset,
        current_user=current_user,
    )
    return ArticleListResponseSchema(articles=articles, articlesCount=total_count)


@router.get("/articles/feed", response_model=ArticleListResponseSchema, tags=["Articles"])
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get articles from followed users (feed).
    Requires authentication.
    """
    service = ArticleService(db)
    articles, total_count = await service.get_feed(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    return ArticleListResponseSchema(articles=articles, articlesCount=total_count)


@router.post(
    "/articles",
    response_model=ArticleResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["Articles"],
)
async def create_article(
    article_data: ArticleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new article.
    Requires authentication.
    """
    service = ArticleService(db)
    article = await service.create_article(
        article_data=article_data.article,
        author=current_user,
    )
    return ArticleResponseSchema(article=article)


@router.get("/articles/{slug}", response_model=ArticleResponseSchema, tags=["Articles"])
async def get_article(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Get an article by slug.
    """
    service = ArticleService(db)
    article = await service.get_article_by_slug(
        slug=slug,
        current_user=current_user,
    )
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    return ArticleResponseSchema(article=article)


@router.put("/articles/{slug}", response_model=ArticleResponseSchema, tags=["Articles"])
async def update_article(
    slug: str,
    article_data: ArticleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an article.
    Requires authentication and ownership.
    """
    service = ArticleService(db)
    article = await service.update_article(
        slug=slug,
        article_data=article_data.article,
        current_user=current_user,
    )
    return ArticleResponseSchema(article=article)


@router.delete(
    "/articles/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Articles"],
)
async def delete_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an article.
    Requires authentication and ownership.
    """
    service = ArticleService(db)
    await service.delete_article(slug=slug, current_user=current_user)
    return None


@router.post(
    "/articles/{slug}/favorite",
    response_model=ArticleResponseSchema,
    tags=["Favorites"],
)
async def favorite_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Favorite an article.
    Requires authentication.
    """
    service = ArticleService(db)
    article = await service.favorite_article(
        slug=slug,
        current_user=current_user,
    )
    return ArticleResponseSchema(article=article)


@router.delete(
    "/articles/{slug}/favorite",
    response_model=ArticleResponseSchema,
    tags=["Favorites"],
)
async def unfavorite_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unfavorite an article.
    Requires authentication.
    """
    service = ArticleService(db)
    article = await service.unfavorite_article(
        slug=slug,
        current_user=current_user,
    )
    return ArticleResponseSchema(article=article)


@router.get(
    "/articles/{slug}/comments",
    response_model=CommentListResponseSchema,
    tags=["Comments"],
)
async def get_comments(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Get comments for an article.
    """
    service = CommentService(db)
    comments = await service.get_comments_for_article(
        slug=slug,
        current_user=current_user,
    )
    return CommentListResponseSchema(comments=comments)


@router.post(
    "/articles/{slug}/comments",
    response_model=CommentResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["Comments"],
)
async def add_comment(
    slug: str,
    comment_data: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a comment to an article.
    Requires authentication.
    """
    service = CommentService(db)
    comment = await service.add_comment(
        slug=slug,
        comment_data=comment_data.comment,
        author=current_user,
    )
    return CommentResponseSchema(comment=comment)


@router.delete(
    "/articles/{slug}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Comments"],
)
async def delete_comment(
    slug: str,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a comment.
    Requires authentication and ownership.
    """
    service = CommentService(db)
    await service.delete_comment(
        slug=slug,
        comment_id=comment_id,
        current_user=current_user,
    )
    return None


@router.get("/tags", response_model=TagListResponseSchema, tags=["Tags"])
async def get_tags(
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of all tags.
    """
    service = TagService(db)
    tags = await service.get_all_tags()
    return TagListResponseSchema(tags=tags)
