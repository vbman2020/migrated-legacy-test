"""Business logic for articles, comments, and tags."""
import logging
import re
import secrets
import string
import unicodedata
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.articles.models import Article, Comment, Tag, article_favorites
from app.articles.schemas import (
    ArticleCreate,
    ArticleResponse,
    ArticleUpdate,
    CommentCreate,
    CommentResponse,
)
from app.profiles.models import Profile
from app.profiles.schemas import ProfileResponse
from app.auth.models import User

logger = logging.getLogger(__name__)

MAX_SLUG_LENGTH = 255
MAX_SLUG_RETRIES = 10
MAX_ARTICLE_BODY_LENGTH = 100000
MAX_COMMENT_BODY_LENGTH = 10000
MAX_PAGINATION_OFFSET = 100000


def generate_random_string(length: int = 8) -> str:
    """Generate a random string for slug uniqueness."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def slugify(text: str) -> str:
    """Convert text to slug format with proper Unicode handling.
    
    Args:
        text: The text to convert to slug format
        
    Returns:
        str: Slugified text
        
    Raises:
        ValueError: If text is empty or results in empty slug
    """
    if not text or not text.strip():
        raise ValueError("Cannot slugify empty text")
    
    # Normalize Unicode characters to ASCII
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    
    # Remove leading/trailing hyphens
    text = text.strip('-')
    
    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)
    
    if not text:
        raise ValueError("Slugified text resulted in empty string")
    
    return text


async def generate_unique_slug(
    db: AsyncSession, title: str, max_length: int = MAX_SLUG_LENGTH, max_retries: int = MAX_SLUG_RETRIES
) -> str:
    """Generate a unique slug from title with random suffix and database-level retry.
    
    Args:
        db: Database session
        title: Article title to generate slug from
        max_length: Maximum length of slug
        max_retries: Maximum number of retry attempts
        
    Returns:
        str: Unique slug
        
    Raises:
        ValueError: If unable to generate unique slug or title is invalid
    """
    try:
        base_slug = slugify(title)
    except ValueError as e:
        raise ValueError(f"Invalid title for slug generation: {str(e)}")
    
    for attempt in range(max_retries):
        unique = generate_random_string()
        slug = base_slug
        
        # Truncate slug if necessary to fit unique suffix
        if len(slug) > max_length:
            slug = slug[:max_length]

        while len(slug + "-" + unique) > max_length:
            parts = slug.split("-")
            if len(parts) == 1:
                # No hyphens, truncate from end
                slug = slug[: max_length - len(unique) - 1]
                break
            else:
                # Remove last part
                slug = "-".join(parts[:-1])
        
        final_slug = slug + "-" + unique
        
        # Check if slug exists in database
        result = await db.execute(select(Article).where(Article.slug == final_slug))
        if result.scalar_one_or_none() is None:
            return final_slug
        
        logger.warning(f"Slug collision detected on attempt {attempt + 1}: {final_slug}")
    
    # If we've exhausted retries, raise an error
    raise ValueError(
        f"Failed to generate unique slug after {max_retries} attempts. "
        "This may indicate a database issue or extremely high collision rate."
    )


async def get_or_create_tag(db: AsyncSession, tag_name: str) -> Tag:
    """Get existing tag or create new one.
    
    Args:
        db: Database session
        tag_name: Name of the tag
        
    Returns:
        Tag: The tag object
    """
    # Sanitize tag name
    tag_name = tag_name.strip()[:255]
    if not tag_name:
        raise ValueError("Tag name cannot be empty")
    
    # Use tag name directly as unique identifier (case-insensitive)
    tag_lower = tag_name.lower()
    
    # Try to get existing tag (case-insensitive search)
    result = await db.execute(
        select(Tag).where(func.lower(Tag.tag) == tag_lower)
    )
    tag = result.scalar_one_or_none()
    
    if tag is None:
        tag = Tag(tag=tag_name)
        db.add(tag)
        try:
            await db.flush()
        except IntegrityError:
            # Handle race condition - another transaction created the tag
            await db.rollback()
            result = await db.execute(
                select(Tag).where(func.lower(Tag.tag) == tag_lower)
            )
            tag = result.scalar_one_or_none()
            if tag is None:
                raise ValueError(f"Failed to create or retrieve tag: {tag_name}")
    
    return tag


async def create_article(
    db: AsyncSession, article_data: ArticleCreate, author: Profile
) -> Article:
    """Create a new article.
    
    Args:
        db: Database session
        article_data: Article creation data
        author: Author profile
        
    Returns:
        Article: Created article
        
    Raises:
        ValueError: If article creation fails
    """
    logger.info(f"Creating article '{article_data.title}' by user {author.id}")
    
    # Validate body length
    if len(article_data.body) > MAX_ARTICLE_BODY_LENGTH:
        raise ValueError(f"Article body exceeds maximum length of {MAX_ARTICLE_BODY_LENGTH} characters")
    
    # Generate unique slug with proper error handling
    try:
        slug = await generate_unique_slug(db, article_data.title)
    except ValueError as e:
        logger.error(f"Failed to generate slug: {e}")
        raise ValueError(f"Failed to generate article slug: {str(e)}")

    # Create article
    article = Article(
        slug=slug,
        title=article_data.title,
        description=article_data.description,
        body=article_data.body,
        author_id=author.id,
    )
    db.add(article)
    
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"IntegrityError creating article: {e}")
        raise ValueError("Failed to create article due to database constraint violation")

    # Handle tags
    if article_data.tagList:
        for tag_name in article_data.tagList:
            try:
                tag = await get_or_create_tag(db, tag_name)
                article.tags.append(tag)
            except ValueError as e:
                logger.warning(f"Failed to add tag '{tag_name}': {e}")
                # Continue with other tags

    try:
        await db.commit()
        await db.refresh(article)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error committing article: {e}")
        raise ValueError("Failed to save article")
    
    logger.info(f"Article created with slug: {article.slug}")
    return article


async def get_article_by_slug(
    db: AsyncSession, slug: str, load_relations: bool = True
) -> Optional[Article]:
    """Get article by slug with optional relationship loading.
    
    Args:
        db: Database session
        slug: Article slug
        load_relations: Whether to load relationships
        
    Returns:
        Optional[Article]: The article if found, None otherwise
    """
    query = select(Article).where(Article.slug == slug)
    
    if load_relations:
        query = query.options(
            joinedload(Article.author).joinedload(Profile.user),
            selectinload(Article.tags),
            selectinload(Article.favorited_by),
        )
    
    result = await db.execute(query)
    return result.unique().scalar_one_or_none()


async def update_article(
    db: AsyncSession, article: Article, article_data: ArticleUpdate
) -> Article:
    """Update an existing article.
    
    Args:
        db: Database session
        article: Article to update
        article_data: Update data
        
    Returns:
        Article: Updated article
        
    Raises:
        ValueError: If update fails
    """
    logger.info(f"Updating article with slug: {article.slug}")
    
    update_data = article_data.model_dump(exclude_unset=True)
    
    # Handle tags separately
    tag_list = update_data.pop("tagList", None)
    
    # Validate body length if provided
    if "body" in update_data and len(update_data["body"]) > MAX_ARTICLE_BODY_LENGTH:
        raise ValueError(f"Article body exceeds maximum length of {MAX_ARTICLE_BODY_LENGTH} characters")
    
    # Update slug if title changed
    if "title" in update_data:
        try:
            new_slug = await generate_unique_slug(db, update_data["title"])
            article.slug = new_slug
        except ValueError as e:
            logger.error(f"Failed to generate new slug: {e}")
            raise ValueError(f"Failed to generate article slug: {str(e)}")
    
    # Update basic fields
    for field, value in update_data.items():
        setattr(article, field, value)
    
    # Update tags if provided
    if tag_list is not None:
        article.tags.clear()
        for tag_name in tag_list:
            try:
                tag = await get_or_create_tag(db, tag_name)
                article.tags.append(tag)
            except ValueError as e:
                logger.warning(f"Failed to add tag '{tag_name}': {e}")
                # Continue with other tags
    
    # Note: updated_at will be automatically updated by onupdate in model
    
    try:
        await db.commit()
        await db.refresh(article)
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"IntegrityError updating article: {e}")
        raise ValueError("Failed to update article due to database constraint violation")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating article: {e}")
        raise ValueError("Failed to update article")
    
    logger.info(f"Article updated: {article.slug}")
    return article


async def delete_article(db: AsyncSession, article: Article) -> None:
    """Delete an article.
    
    Args:
        db: Database session
        article: Article to delete
    """
    logger.info(f"Deleting article with slug: {article.slug}")
    
    try:
        await db.delete(article)
        await db.commit()
        logger.info(f"Article deleted: {article.slug}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting article: {e}")
        raise ValueError("Failed to delete article")


async def list_articles(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    author: Optional[str] = None,
    tag: Optional[str] = None,
    favorited: Optional[str] = None,
) -> tuple[List[Article], int]:
    """List articles with filters and pagination.
    
    Args:
        db: Database session
        limit: Maximum number of articles to return
        offset: Number of articles to skip
        author: Filter by author username
        tag: Filter by tag
        favorited: Filter by user who favorited
        
    Returns:
        tuple: (list of articles, total count)
        
    Raises:
        ValueError: If pagination parameters are invalid
    """
    # Validate pagination
    if offset > MAX_PAGINATION_OFFSET:
        raise ValueError(f"Offset exceeds maximum allowed value of {MAX_PAGINATION_OFFSET}")
    
    query = select(Article).options(
        joinedload(Article.author).joinedload(Profile.user),
        selectinload(Article.tags),
        selectinload(Article.favorited_by),
    )

    # Apply filters with proper joins
    if author:
        # Sanitize input
        author = author.strip()
        query = query.join(Article.author).join(Profile.user).where(
            func.lower(User.username) == author.lower()
        )
    
    if tag:
        # Sanitize input
        tag = tag.strip()
        query = query.join(Article.tags).where(func.lower(Tag.tag) == tag.lower())
    
    if favorited:
        # Sanitize input
        favorited = favorited.strip()
        query = query.join(Article.favorited_by).join(Profile.user).where(
            func.lower(User.username) == favorited.lower()
        )

    # Get total count - create count query from the filtered query
    count_query = select(func.count()).select_from(
        query.with_only_columns(Article.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(Article.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    articles = list(result.unique().scalars().all())
    
    return articles, total


async def get_feed(
    db: AsyncSession, user_profile: Profile, limit: int = 20, offset: int = 0
) -> tuple[List[Article], int]:
    """Get feed of articles from followed users.
    
    Args:
        db: Database session
        user_profile: Current user's profile
        limit: Maximum number of articles to return
        offset: Number of articles to skip
        
    Returns:
        tuple: (list of articles, total count)
        
    Raises:
        ValueError: If pagination parameters are invalid
    """
    # Validate pagination
    if offset > MAX_PAGINATION_OFFSET:
        raise ValueError(f"Offset exceeds maximum allowed value of {MAX_PAGINATION_OFFSET}")
    
    # Get IDs of profiles that the user follows
    followed_ids = [profile.id for profile in user_profile.following]
    
    if not followed_ids:
        # User doesn't follow anyone, return empty list
        return [], 0
    
    query = (
        select(Article)
        .where(Article.author_id.in_(followed_ids))
        .options(
            joinedload(Article.author).joinedload(Profile.user),
            selectinload(Article.tags),
            selectinload(Article.favorited_by),
        )
    )
    
    # Get total count
    count_query = select(func.count()).select_from(
        query.with_only_columns(Article.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination and ordering
    query = query.order_by(Article.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    articles = list(result.unique().scalars().all())
    
    return articles, total


async def favorite_article(db: AsyncSession, article: Article, profile: Profile) -> Article:
    """Favorite an article.
    
    Args:
        db: Database session
        article: Article to favorite
        profile: User profile favoriting the article
        
    Returns:
        Article: Updated article
    """
    logger.info(f"User {profile.id} favoriting article {article.id}")
    
    if profile not in article.favorited_by:
        article.favorited_by.append(profile)
        try:
            await db.commit()
            await db.refresh(article)
        except Exception as e:
            await db.rollback()
            logger.error(f"Error favoriting article: {e}")
            raise ValueError("Failed to favorite article")
    
    return article


async def unfavorite_article(db: AsyncSession, article: Article, profile: Profile) -> Article:
    """Unfavorite an article.
    
    Args:
        db: Database session
        article: Article to unfavorite
        profile: User profile unfavoriting the article
        
    Returns:
        Article: Updated article
    """
    logger.info(f"User {profile.id} unfavoriting article {article.id}")
    
    if profile in article.favorited_by:
        article.favorited_by.remove(profile)
        try:
            await db.commit()
            await db.refresh(article)
        except Exception as e:
            await db.rollback()
            logger.error(f"Error unfavoriting article: {e}")
            raise ValueError("Failed to unfavorite article")
    
    return article


async def is_article_favorited(db: AsyncSession, article: Article, profile: Profile) -> bool:
    """Check if article is favorited by profile.
    
    Args:
        db: Database session
        article: Article to check
        profile: User profile to check
        
    Returns:
        bool: True if the article is favorited by the profile, False otherwise.
    """
    result = await db.execute(
        select(article_favorites).where(
            and_(
                article_favorites.c.article_id == article.id,
                article_favorites.c.profile_id == profile.id,
            )
        )
    )
    return result.first() is not None


async def get_favorites_count(db: AsyncSession, article: Article) -> int:
    """Get favorites count for article.
    
    Args:
        db: Database session
        article: Article to count favorites for
        
    Returns:
        int: The number of times this article has been favorited.
    """
    result = await db.execute(
        select(func.count()).select_from(article_favorites).where(
            article_favorites.c.article_id == article.id
        )
    )
    return result.scalar() or 0


async def create_comment(
    db: AsyncSession, article: Article, comment_data: CommentCreate, author: Profile
) -> Comment:
    """Create a comment on an article.
    
    Args:
        db: Database session
        article: Article to comment on
        comment_data: Comment creation data
        author: Comment author
        
    Returns:
        Comment: Created comment
        
    Raises:
        ValueError: If comment creation fails
    """
    logger.info(f"User {author.id} creating comment on article {article.id}")
    
    # Validate body length
    if len(comment_data.body) > MAX_COMMENT_BODY_LENGTH:
        raise ValueError(f"Comment body exceeds maximum length of {MAX_COMMENT_BODY_LENGTH} characters")
    
    comment = Comment(
        body=comment_data.body,
        article_id=article.id,
        author_id=author.id,
    )
    db.add(comment)
    
    try:
        await db.commit()
        await db.refresh(comment)
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"IntegrityError creating comment: {e}")
        raise ValueError("Failed to create comment due to database constraint violation")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating comment: {e}")
        raise ValueError("Failed to create comment")
    
    logger.info(f"Comment created with id: {comment.id}")
    return comment


async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Optional[Comment]:
    """Get comment by ID with author relationship loaded.
    
    Args:
        db: Database session
        comment_id: Comment ID
        
    Returns:
        Optional[Comment]: The comment if found, None otherwise
    """
    query = select(Comment).where(Comment.id == comment_id).options(
        joinedload(Comment.author).joinedload(Profile.user)
    )
    result = await db.execute(query)
    return result.unique().scalar_one_or_none()


async def list_comments(db: AsyncSession, article: Article) -> List[Comment]:
    """List all comments for an article.
    
    Args:
        db: Database session
        article: Article to get comments for
        
    Returns:
        List[Comment]: List of comments
    """
    query = (
        select(Comment)
        .where(Comment.article_id == article.id)
        .options(joinedload(Comment.author).joinedload(Profile.user))
        .order_by(Comment.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def delete_comment(db: AsyncSession, comment: Comment) -> None:
    """Delete a comment.
    
    Args:
        db: Database session
        comment: Comment to delete
    """
    logger.info(f"Deleting comment with id: {comment.id}")
    
    try:
        await db.delete(comment)
        await db.commit()
        logger.info(f"Comment deleted: {comment.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting comment: {e}")
        raise ValueError("Failed to delete comment")


async def get_all_tags(db: AsyncSession) -> List[Tag]:
    """Get all tags ordered alphabetically.
    
    Args:
        db: Database session
        
    Returns:
        List[Tag]: List of all tags
    """
    result = await db.execute(select(Tag).order_by(Tag.tag))
    return list(result.scalars().all())


def article_to_response(
    article: Article, current_user_profile: Optional[Profile] = None
) -> ArticleResponse:
    """Convert Article model to ArticleResponse schema.
    
    Args:
        article: Article model instance
        current_user_profile: Current user's profile (for favorited/following status)
        
    Returns:
        ArticleResponse: Article response schema
    """
    favorited = False
    if current_user_profile:
        favorited = current_user_profile in article.favorited_by
    
    return ArticleResponse(
        slug=article.slug,
        title=article.title,
        description=article.description,
        body=article.body,
        tagList=[tag.tag for tag in article.tags],
        createdAt=article.created_at,
        updatedAt=article.updated_at,
        favorited=favorited,
        favoritesCount=len(article.favorited_by),
        author=ProfileResponse(
            username=article.author.user.username,
            bio=article.author.bio or "",
            image=article.author.image or "",
            following=(
                current_user_profile in article.author.followers
                if current_user_profile
                else False
            ),
        ),
    )


def comment_to_response(
    comment: Comment, current_user_profile: Optional[Profile] = None
) -> CommentResponse:
    """Convert Comment model to CommentResponse schema.
    
    Args:
        comment: Comment model instance
        current_user_profile: Current user's profile (for following status)
        
    Returns:
        CommentResponse: Comment response schema
    """
    return CommentResponse(
        id=comment.id,
        createdAt=comment.created_at,
        updatedAt=comment.updated_at,
        body=comment.body,
        author=ProfileResponse(
            username=comment.author.user.username,
            bio=comment.author.bio or "",
            image=comment.author.image or "",
            following=(
                current_user_profile in comment.author.followers
                if current_user_profile
                else False
            ),
        ),
    )
