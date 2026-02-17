from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user, get_current_user_optional
from app.articles import service
from app.articles.schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleResponseWrapper,
    MultipleArticlesResponse,
    CommentCreate,
    CommentResponseWrapper,
    MultipleCommentsResponse,
    TagsResponse,
)

router = APIRouter()


@router.get("/articles", response_model=MultipleArticlesResponse, tags=["articles"])
async def list_articles(
    tag: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    favorited: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """List articles with optional filtering by tag, author, or favorited user."""
    articles, total_count = await service.get_articles(
        db=db,
        tag=tag,
        author=author,
        favorited=favorited,
        limit=limit,
        offset=offset,
        current_user=current_user,
    )
    
    article_responses = await service.articles_to_response_batch(articles, current_user, db)
    
    return MultipleArticlesResponse(
        articles=article_responses,
        articles_count=total_count,
    )


@router.get("/articles/feed", response_model=MultipleArticlesResponse, tags=["articles"])
async def get_articles_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get articles from followed users."""
    articles, total_count = await service.get_feed(
        db=db,
        user=current_user,
        limit=limit,
        offset=offset,
    )
    
    article_responses = await service.articles_to_response_batch(articles, current_user, db)
    
    return MultipleArticlesResponse(
        articles=article_responses,
        articles_count=total_count,
    )


@router.post("/articles", response_model=ArticleResponseWrapper, status_code=status.HTTP_201_CREATED, tags=["articles"])
async def create_article(
    article_data: ArticleCreate = Body(..., embed=True, alias="article"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new article."""
    article = await service.create_article(
        db=db,
        article_data=article_data,
        author=current_user,
    )
    
    article_response = await service.article_to_response(article, current_user, db)
    return ArticleResponseWrapper(article=article_response)


@router.get("/articles/{slug}", response_model=ArticleResponseWrapper, tags=["articles"])
async def get_article(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get an article by slug."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    article_response = await service.article_to_response(article, current_user, db)
    return ArticleResponseWrapper(article=article_response)


@router.put("/articles/{slug}", response_model=ArticleResponseWrapper, tags=["articles"])
async def update_article(
    slug: str,
    article_data: ArticleUpdate = Body(..., embed=True, alias="article"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an article."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    if article.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this article.",
        )
    
    article = await service.update_article(
        db=db,
        article=article,
        article_data=article_data,
    )
    
    article_response = await service.article_to_response(article, current_user, db)
    return ArticleResponseWrapper(article=article_response)


@router.delete("/articles/{slug}", status_code=status.HTTP_204_NO_CONTENT, tags=["articles"])
async def delete_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an article."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    if article.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this article.",
        )
    
    await service.delete_article(db=db, article=article)


@router.post("/articles/{slug}/favorite", response_model=ArticleResponseWrapper, status_code=status.HTTP_201_CREATED, tags=["articles"])
async def favorite_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Favorite an article."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug was not found.",
        )
    
    await service.favorite_article(db=db, article=article, user=current_user)
    
    # Reload article to get updated favorites
    article = await service.get_article_by_slug(db=db, slug=slug)
    article_response = await service.article_to_response(article, current_user, db)
    return ArticleResponseWrapper(article=article_response)


@router.delete("/articles/{slug}/favorite", response_model=ArticleResponseWrapper, tags=["articles"])
async def unfavorite_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unfavorite an article."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug was not found.",
        )
    
    await service.unfavorite_article(db=db, article=article, user=current_user)
    
    # Reload article to get updated favorites
    article = await service.get_article_by_slug(db=db, slug=slug)
    article_response = await service.article_to_response(article, current_user, db)
    return ArticleResponseWrapper(article=article_response)


@router.get("/articles/{slug}/comments", response_model=MultipleCommentsResponse, tags=["comments"])
async def get_comments(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get comments for an article."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    comments = await service.get_comments_for_article(db=db, article_id=article.id)
    
    comment_responses = await service.comments_to_response_batch(comments, current_user, db)
    
    return MultipleCommentsResponse(comments=comment_responses)


@router.post("/articles/{slug}/comments", response_model=CommentResponseWrapper, status_code=status.HTTP_201_CREATED, tags=["comments"])
async def create_comment(
    slug: str,
    comment_data: CommentCreate = Body(..., embed=True, alias="comment"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to an article."""
    article = await service.get_article_by_slug(db=db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An article with this slug does not exist.",
        )
    
    comment = await service.create_comment(
        db=db,
        article=article,
        comment_data=comment_data,
        author=current_user,
    )
    
    comment_response = await service.comment_to_response(comment, current_user, db)
    return CommentResponseWrapper(comment=comment_response)


@router.delete("/articles/{slug}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["comments"])
async def delete_comment(
    slug: str,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment."""
    comment = await service.get_comment_by_id(db=db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A comment with this ID does not exist.",
        )
    
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this comment.",
        )
    
    await service.delete_comment(db=db, comment=comment)


@router.get("/tags", response_model=TagsResponse, tags=["tags"])
async def get_tags(
    db: AsyncSession = Depends(get_db),
):
    """Get all tags."""
    tags = await service.get_all_tags(db=db)
    return TagsResponse(tags=tags)
