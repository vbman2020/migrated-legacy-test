"""FastAPI router for article endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles.models import Article, Comment
from app.articles.schemas import (
    ArticleCreateRequest,
    ArticleListResponse,
    ArticleResponseWrapper,
    ArticleUpdateRequest,
    CommentCreateRequest,
    CommentListResponse,
    CommentResponseWrapper,
    TagListResponse,
)
from app.articles.service import (
    article_to_response,
    comment_to_response,
    create_article,
    create_comment,
    delete_article,
    delete_comment,
    favorite_article,
    get_all_tags,
    get_article_by_slug,
    get_comment_by_id,
    get_feed,
    list_articles,
    list_comments,
    unfavorite_article,
    update_article,
)
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.profiles.models import Profile

router = APIRouter()


@router.post(
    "/articles",
    response_model=ArticleResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["articles"],
)
async def create_article_endpoint(
    request: ArticleCreateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponseWrapper:
    """Create a new article."""
    try:
        article = await create_article(db, request.article, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Reload with relationships
    article = await get_article_by_slug(db, article.slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create article",
        )
    
    return ArticleResponseWrapper(
        article=article_to_response(article, current_user)
    )


@router.get(
    "/articles",
    response_model=ArticleListResponse,
    tags=["articles"],
)
async def list_articles_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tag: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    favorited: Optional[str] = Query(None),
    current_user: Optional[Profile] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    """List articles with optional filters."""
    try:
        articles, total = await list_articles(
            db,
            limit=limit,
            offset=offset,
            author=author,
            tag=tag,
            favorited=favorited,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return ArticleListResponse(
        articles=[
            article_to_response(article, current_user) for article in articles
        ],
        articlesCount=total,
    )


@router.get(
    "/articles/feed",
    response_model=ArticleListResponse,
    tags=["articles"],
)
async def get_feed_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    """Get feed of articles from followed users."""
    try:
        articles, total = await get_feed(db, current_user, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return ArticleListResponse(
        articles=[
            article_to_response(article, current_user) for article in articles
        ],
        articlesCount=total,
    )


@router.get(
    "/articles/{slug}",
    response_model=ArticleResponseWrapper,
    tags=["articles"],
)
async def get_article_endpoint(
    slug: str,
    current_user: Optional[Profile] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponseWrapper:
    """Get article by slug."""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    return ArticleResponseWrapper(
        article=article_to_response(article, current_user)
    )


@router.put(
    "/articles/{slug}",
    response_model=ArticleResponseWrapper,
    tags=["articles"],
)
async def update_article_endpoint(
    slug: str,
    request: ArticleUpdateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponseWrapper:
    """Update an article."""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    # Check if user is the author
    if article.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this article.",
        )
    
    try:
        article = await update_article(db, article, request.article)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Reload with relationships
    article = await get_article_by_slug(db, article.slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update article",
        )
    
    return ArticleResponseWrapper(
        article=article_to_response(article, current_user)
    )


@router.delete(
    "/articles/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["articles"],
)
async def delete_article_endpoint(
    slug: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an article."""
    article = await get_article_by_slug(db, slug, load_relations=False)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    # Check if user is the author
    if article.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this article.",
        )
    
    try:
        await delete_article(db, article)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/articles/{slug}/favorite",
    response_model=ArticleResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["articles"],
)
async def favorite_article_endpoint(
    slug: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponseWrapper:
    """Favorite an article."""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug was not found.",
        )
    
    try:
        article = await favorite_article(db, article, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    
    return ArticleResponseWrapper(
        article=article_to_response(article, current_user)
    )


@router.delete(
    "/articles/{slug}/favorite",
    response_model=ArticleResponseWrapper,
    tags=["articles"],
)
async def unfavorite_article_endpoint(
    slug: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleResponseWrapper:
    """Unfavorite an article."""
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug was not found.",
        )
    
    try:
        article = await unfavorite_article(db, article, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    
    return ArticleResponseWrapper(
        article=article_to_response(article, current_user)
    )


@router.get(
    "/articles/{slug}/comments",
    response_model=CommentListResponse,
    tags=["articles"],
)
async def list_comments_endpoint(
    slug: str,
    current_user: Optional[Profile] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """Get comments for an article."""
    article = await get_article_by_slug(db, slug, load_relations=False)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    comments = await list_comments(db, article)
    
    return CommentListResponse(
        comments=[
            comment_to_response(comment, current_user) for comment in comments
        ]
    )


@router.post(
    "/articles/{slug}/comments",
    response_model=CommentResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    tags=["articles"],
)
async def create_comment_endpoint(
    slug: str,
    request: CommentCreateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponseWrapper:
    """Add a comment to an article."""
    article = await get_article_by_slug(db, slug, load_relations=False)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    try:
        comment = await create_comment(db, article, request.comment, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Reload with relationships
    comment = await get_comment_by_id(db, comment.id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create comment",
        )
    
    return CommentResponseWrapper(
        comment=comment_to_response(comment, current_user)
    )


@router.delete(
    "/articles/{slug}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["articles"],
)
async def delete_comment_endpoint(
    slug: str,
    comment_id: int,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a comment."""
    # Verify article exists first
    article = await get_article_by_slug(db, slug, load_relations=False)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A comment with this ID does not exist.",
        )
    
    # Verify comment belongs to article
    if comment.article_id != article.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A comment with this ID does not exist for this article.",
        )
    
    # Check if user is the author
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this comment.",
        )
    
    try:
        await delete_comment(db, comment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/tags",
    response_model=TagListResponse,
    tags=["tags"],
)
async def list_tags_endpoint(
    db: AsyncSession = Depends(get_db),
) -> TagListResponse:
    """Get all tags."""
    tags = await get_all_tags(db)
    return TagListResponse(tags=[tag.tag for tag in tags])
