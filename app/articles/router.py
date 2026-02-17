from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles.schemas import (
    ArticleCreateWrapper,
    ArticleListResponse,
    ArticleResponseWrapper,
    ArticleUpdateWrapper,
    CommentCreateWrapper,
    CommentListResponse,
    CommentResponseWrapper,
    TagsResponse,
)
from app.articles.service import ArticleService
from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, get_optional_current_user

router = APIRouter()


@router.get("/articles", response_model=ArticleListResponse, tags=["articles"])
async def list_articles(
    tag: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    favorited: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List articles with optional filtering by tag, author, or favorited user.
    Supports pagination with limit and offset.
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
    return ArticleListResponse(articles=articles, articlesCount=total_count)


@router.get("/articles/feed", response_model=ArticleListResponse, tags=["articles"])
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get feed of articles from followed users (requires authentication).
    """
    service = ArticleService(db)
    articles, total_count = await service.get_feed(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    return ArticleListResponse(articles=articles, articlesCount=total_count)


@router.post(
    "/articles",
    response_model=ArticleResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["articles"],
)
async def create_article(
    article_wrapper: ArticleCreateWrapper,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new article (requires authentication).
    Expected format: {"article": {"title": "...", "description": "...", "body": "...", "tagList": [...]}}
    """
    service = ArticleService(db)
    article = await service.create_article(
        article_data=article_wrapper.article,
        author=current_user,
    )
    return ArticleResponseWrapper(article=article)


@router.get("/articles/{slug}", response_model=ArticleResponseWrapper, tags=["articles"])
async def get_article(
    slug: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single article by slug.
    """
    service = ArticleService(db)
    article = await service.get_article_by_slug(slug=slug, current_user=current_user)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    return ArticleResponseWrapper(article=article)


@router.put("/articles/{slug}", response_model=ArticleResponseWrapper, tags=["articles"])
async def update_article(
    slug: str,
    article_wrapper: ArticleUpdateWrapper,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an article (requires authentication and ownership).
    Expected format: {"article": {"title": "...", "description": "...", "body": "..."}}
    """
    service = ArticleService(db)
    article = await service.update_article(
        slug=slug,
        article_data=article_wrapper.article,
        current_user=current_user,
    )
    return ArticleResponseWrapper(article=article)


@router.delete(
    "/articles/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["articles"],
)
async def delete_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an article (requires authentication and ownership).
    """
    service = ArticleService(db)
    await service.delete_article(slug=slug, current_user=current_user)
    return None


@router.post(
    "/articles/{slug}/favorite",
    response_model=ArticleResponseWrapper,
    status_code=status.HTTP_200_OK,
    tags=["articles"],
)
async def favorite_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Favorite an article (requires authentication).
    """
    service = ArticleService(db)
    article = await service.favorite_article(slug=slug, current_user=current_user)
    return ArticleResponseWrapper(article=article)


@router.delete(
    "/articles/{slug}/favorite",
    response_model=ArticleResponseWrapper,
    tags=["articles"],
)
async def unfavorite_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unfavorite an article (requires authentication).
    """
    service = ArticleService(db)
    article = await service.unfavorite_article(slug=slug, current_user=current_user)
    return ArticleResponseWrapper(article=article)


@router.get(
    "/articles/{slug}/comments",
    response_model=CommentListResponse,
    tags=["comments"],
)
async def get_comments(
    slug: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all comments for an article.
    """
    service = ArticleService(db)
    comments = await service.get_comments(slug=slug, current_user=current_user)
    return CommentListResponse(comments=comments)


@router.post(
    "/articles/{slug}/comments",
    response_model=CommentResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["comments"],
)
async def create_comment(
    slug: str,
    comment_wrapper: CommentCreateWrapper,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a comment to an article (requires authentication).
    Expected format: {"comment": {"body": "..."}}
    """
    service = ArticleService(db)
    comment = await service.create_comment(
        slug=slug,
        comment_data=comment_wrapper.comment,
        author=current_user,
    )
    return CommentResponseWrapper(comment=comment)


@router.delete(
    "/articles/{slug}/comments/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["comments"],
)
async def delete_comment(
    slug: str,
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a comment (requires authentication and ownership).
    """
    service = ArticleService(db)
    await service.delete_comment(
        slug=slug,
        comment_id=id,
        current_user=current_user,
    )
    return None


@router.get("/tags", response_model=TagsResponse, tags=["tags"])
async def get_tags(
    db: AsyncSession = Depends(get_db),
):
    """
    Get all tags.
    """
    service = ArticleService(db)
    tags = await service.get_all_tags()
    return TagsResponse(tags=tags)
