import html
import logging
import re
import secrets
import string
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.articles.models import Article, Comment, Tag, article_favorites
from app.articles.schemas import (
    ArticleCreate,
    ArticleResponse,
    ArticleUpdate,
    CommentCreate,
    CommentResponse,
    ProfileSchema,
)
from app.auth.models import User

# Configuration constants
MAXIMUM_SLUG_LENGTH = 255
UNIQUE_STRING_LENGTH = 6
MAX_SLUG_GENERATION_ATTEMPTS = 10

# Set up logging
logger = logging.getLogger(__name__)


class ArticleService:
    """Service class for article-related business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_random_string(self, length: int = UNIQUE_STRING_LENGTH) -> str:
        """Generate a cryptographically secure random string for unique slugs.
        
        Args:
            length: Length of the random string to generate.
            
        Returns:
            A random string of lowercase letters and digits.
        """
        alphabet = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _slugify(self, text: str) -> str:
        """Convert text to slug format with XSS prevention.
        
        This method sanitizes input by:
        - Converting to lowercase
        - Replacing spaces/underscores with hyphens
        - Removing all non-alphanumeric characters except hyphens
        - Removing multiple consecutive hyphens
        - Stripping hyphens from start and end
        
        Args:
            text: The text to convert to a slug.
            
        Returns:
            A sanitized slug string.
        """
        # HTML escape first to prevent any HTML injection
        text = html.escape(text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace spaces and underscores with hyphens
        text = re.sub(r'[\s_]+', '-', text)
        
        # Remove all non-alphanumeric characters except hyphens (XSS prevention)
        text = re.sub(r'[^a-z0-9-]', '', text)
        
        # Remove multiple consecutive hyphens
        text = re.sub(r'-+', '-', text)
        
        # Strip hyphens from start and end
        text = text.strip('-')
        
        return text

    def _sanitize_content(self, content: str) -> str:
        """Sanitize content to prevent XSS attacks.
        
        Escapes HTML entities in user-provided content.
        
        Args:
            content: The content to sanitize.
            
        Returns:
            Sanitized content with HTML entities escaped.
        """
        return html.escape(content)

    async def _generate_unique_slug(self, title: str) -> str:
        """Generate a unique slug from title with collision prevention.
        
        This method attempts to generate a unique slug by:
        1. Slugifying the title
        2. Adding a random suffix
        3. Checking for uniqueness in the database
        4. Retrying with a new random suffix if collision occurs
        
        Args:
            title: The article title to generate a slug from.
            
        Returns:
            A unique slug string.
            
        Raises:
            HTTPException: If unable to generate unique slug after max attempts.
        """
        base_slug = self._slugify(title)
        
        # Handle empty slug
        if not base_slug:
            base_slug = "article"
        
        # Ensure we have enough space for the unique string and hyphen
        max_base_length = MAXIMUM_SLUG_LENGTH - UNIQUE_STRING_LENGTH - 1
        
        if max_base_length <= 0:
            logger.error("Slug configuration error: MAXIMUM_SLUG_LENGTH too small")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
        
        # Truncate base_slug if needed
        if len(base_slug) > max_base_length:
            base_slug = base_slug[:max_base_length]
        
        # Continue truncating by removing hyphenated parts if still too long
        while len(base_slug + "-" + "x" * UNIQUE_STRING_LENGTH) > MAXIMUM_SLUG_LENGTH:
            parts = base_slug.split("-")
            if len(parts) == 1:
                # No hyphens, truncate arbitrarily
                base_slug = base_slug[:max_base_length]
                break
            else:
                # Remove last part
                base_slug = "-".join(parts[:-1])
        
        # Try to generate a unique slug with retries
        for attempt in range(MAX_SLUG_GENERATION_ATTEMPTS):
            unique = self._generate_random_string(UNIQUE_STRING_LENGTH)
            candidate_slug = base_slug + "-" + unique
            
            # Check if slug exists
            try:
                result = await self.db.execute(
                    select(exists().where(Article.slug == candidate_slug))
                )
                slug_exists = result.scalar()
                
                if not slug_exists:
                    return candidate_slug
            except SQLAlchemyError as e:
                logger.error(f"Database error checking slug uniqueness: {str(e)}")
                # Continue to next attempt
                continue
        
        # If we couldn't generate a unique slug after max attempts, log and raise error
        logger.error(f"Failed to generate unique slug after {MAX_SLUG_GENERATION_ATTEMPTS} attempts")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    async def _get_or_create_tag(self, tag_name: str) -> Tag:
        """Get existing tag or create a new one with proper sanitization.
        
        This method:
        1. Sanitizes the tag name using HTML escaping
        2. Checks if the tag already exists
        3. Creates a new tag if it doesn't exist
        4. Handles race conditions with retry logic
        
        Args:
            tag_name: The name of the tag to get or create.
            
        Returns:
            A Tag instance.
            
        Raises:
            HTTPException: If tag name is invalid or creation fails.
        """
        # Sanitize tag name to prevent XSS - use HTML escaping for robust protection
        tag_name = tag_name.strip()
        if not tag_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tag name cannot be empty",
            )
        
        # HTML escape to prevent XSS attacks
        tag_name = html.escape(tag_name)
        
        tag_slug = self._slugify(tag_name)
        if not tag_slug:
            tag_slug = "tag-" + self._generate_random_string()
        
        # Try to get existing tag by slug with retry logic for race conditions
        for attempt in range(3):
            try:
                result = await self.db.execute(
                    select(Tag).where(Tag.slug == tag_slug)
                )
                tag = result.scalars().first()
                
                if tag:
                    return tag
                
                # Tag doesn't exist, try to create it
                tag = Tag(tag=tag_name, slug=tag_slug)
                self.db.add(tag)
                await self.db.flush()
                return tag
            except IntegrityError:
                # Another request created the tag, rollback and retry
                await self.db.rollback()
                if attempt < 2:  # Don't log on last attempt
                    logger.warning(f"Tag creation race condition detected for slug: {tag_slug}, retrying...")
                continue
            except SQLAlchemyError as e:
                await self.db.rollback()
                logger.error(f"Database error creating tag: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create tag"
                ) from e
        
        # If we get here, we failed after all retries
        logger.error(f"Failed to get or create tag after retries: {tag_slug}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tag"
        )

    async def _is_following(self, follower_id: int, followed_id: int) -> bool:
        """Check if follower is following followed user.
        
        Uses SQLAlchemy's bound parameters to prevent SQL injection.
        
        Args:
            follower_id: ID of the follower user.
            followed_id: ID of the followed user.
            
        Returns:
            True if following relationship exists, False otherwise.
        """
        from app.auth.models import user_follows
        
        try:
            result = await self.db.execute(
                select(exists().where(
                    and_(
                        user_follows.c.follower_id == follower_id,
                        user_follows.c.followed_id == followed_id
                    )
                ))
            )
            return result.scalar() or False
        except SQLAlchemyError as e:
            logger.error(f"Database error checking follow status: {str(e)}")
            return False

    async def _is_favorited(self, user_id: int, article_id: int) -> bool:
        """Check if user has favorited an article.
        
        Uses SQLAlchemy's bound parameters to prevent SQL injection.
        
        Args:
            user_id: ID of the user.
            article_id: ID of the article.
            
        Returns:
            True if favorite relationship exists, False otherwise.
        """
        try:
            result = await self.db.execute(
                select(exists().where(
                    and_(
                        article_favorites.c.user_id == user_id,
                        article_favorites.c.article_id == article_id
                    )
                ))
            )
            return result.scalar() or False
        except SQLAlchemyError as e:
            logger.error(f"Database error checking favorite status: {str(e)}")
            return False

    async def _get_favorites_count(self, article_id: int) -> int:
        """Get the count of favorites for an article.
        
        Args:
            article_id: ID of the article.
            
        Returns:
            Number of users who favorited the article.
        """
        try:
            result = await self.db.execute(
                select(func.count()).select_from(article_favorites).where(
                    article_favorites.c.article_id == article_id
                )
            )
            return result.scalar() or 0
        except SQLAlchemyError as e:
            logger.error(f"Database error getting favorites count: {str(e)}")
            return 0

    async def _build_profile_schema(
        self, user: User, current_user: Optional[User] = None
    ) -> ProfileSchema:
        """Build a ProfileSchema from a User object.
        
        Args:
            user: The user to build a profile for.
            current_user: The currently authenticated user (optional).
            
        Returns:
            A ProfileSchema instance.
        """
        following = False
        if current_user and current_user.id != user.id:
            following = await self._is_following(current_user.id, user.id)
        
        return ProfileSchema(
            username=user.username,
            bio=user.bio,
            image=user.image,
            following=following,
        )

    async def _build_article_response(
        self, article: Article, current_user: Optional[User] = None
    ) -> ArticleResponse:
        """Build an ArticleResponse from an Article object.
        
        Args:
            article: The article to build a response for.
            current_user: The currently authenticated user (optional).
            
        Returns:
            An ArticleResponse instance.
        """
        favorited = False
        if current_user:
            favorited = await self._is_favorited(current_user.id, article.id)
        
        favorites_count = await self._get_favorites_count(article.id)
        author_profile = await self._build_profile_schema(article.author, current_user)
        
        return ArticleResponse(
            slug=article.slug,
            title=article.title,
            description=article.description,
            body=article.body,
            tagList=[tag.tag for tag in article.tags],
            createdAt=article.created_at,
            updatedAt=article.updated_at,
            favorited=favorited,
            favoritesCount=favorites_count,
            author=author_profile,
        )

    async def _build_comment_response(
        self, comment: Comment, current_user: Optional[User] = None
    ) -> CommentResponse:
        """Build a CommentResponse from a Comment object.
        
        Args:
            comment: The comment to build a response for.
            current_user: The currently authenticated user (optional).
            
        Returns:
            A CommentResponse instance.
        """
        author_profile = await self._build_profile_schema(comment.author, current_user)
        
        return CommentResponse(
            id=comment.id,
            body=comment.body,
            createdAt=comment.created_at,
            updatedAt=comment.updated_at,
            author=author_profile,
        )

    async def list_articles(
        self,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        current_user: Optional[User] = None,
    ) -> Tuple[List[ArticleResponse], int]:
        """List articles with optional filtering and pagination.
        
        Args:
            tag: Filter by tag name.
            author: Filter by author username.
            favorited: Filter by username who favorited.
            limit: Maximum number of articles to return (1-100).
            offset: Number of articles to skip.
            current_user: The currently authenticated user (optional).
            
        Returns:
            A tuple of (list of ArticleResponse, total count).
        """
        try:
            # Validate and sanitize pagination parameters
            if offset < 0:
                offset = 0
            if limit < 1:
                limit = 1
            elif limit > 100:
                limit = 100
            
            # Build base query
            query = (
                select(Article)
                .options(
                    selectinload(Article.author),
                    selectinload(Article.tags),
                )
                .order_by(Article.created_at.desc())
            )

            # Apply filters
            if tag:
                query = query.join(Article.tags).where(Tag.tag == tag)
            
            if author:
                query = query.join(Article.author).where(User.username == author)
            
            if favorited:
                query = query.join(article_favorites).join(
                    User, article_favorites.c.user_id == User.id
                ).where(User.username == favorited)

            # Get total count with same filters
            count_query = select(func.count(Article.id))
            
            if tag:
                count_query = count_query.select_from(Article).join(Article.tags).where(Tag.tag == tag)
            elif author:
                count_query = count_query.select_from(Article).join(Article.author).where(User.username == author)
            elif favorited:
                count_query = count_query.select_from(Article).join(article_favorites).join(
                    User, article_favorites.c.user_id == User.id
                ).where(User.username == favorited)
            else:
                count_query = count_query.select_from(Article)
            
            total_result = await self.db.execute(count_query)
            total_count = total_result.scalar() or 0

            # Apply pagination
            query = query.limit(limit).offset(offset)

            # Execute query
            result = await self.db.execute(query)
            articles = result.unique().scalars().all()

            # Build response objects
            article_responses = []
            for article in articles:
                article_response = await self._build_article_response(article, current_user)
                article_responses.append(article_response)

            return article_responses, total_count
        except SQLAlchemyError as e:
            logger.error(f"Database error listing articles: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve articles"
            ) from e

    async def get_feed(
        self,
        current_user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ArticleResponse], int]:
        """Get feed of articles from followed users.
        
        Args:
            current_user: The currently authenticated user.
            limit: Maximum number of articles to return (1-100).
            offset: Number of articles to skip.
            
        Returns:
            A tuple of (list of ArticleResponse, total count).
        """
        from app.auth.models import user_follows
        
        try:
            # Validate and sanitize pagination parameters
            if offset < 0:
                offset = 0
            if limit < 1:
                limit = 1
            elif limit > 100:
                limit = 100
            
            # Get articles where author is in current_user's following list
            query = (
                select(Article)
                .options(
                    selectinload(Article.author),
                    selectinload(Article.tags),
                )
                .join(user_follows, user_follows.c.followed_id == Article.author_id)
                .where(user_follows.c.follower_id == current_user.id)
                .order_by(Article.created_at.desc())
            )

            # Get total count
            count_query = (
                select(func.count(Article.id))
                .select_from(Article)
                .join(user_follows, user_follows.c.followed_id == Article.author_id)
                .where(user_follows.c.follower_id == current_user.id)
            )
            total_result = await self.db.execute(count_query)
            total_count = total_result.scalar() or 0

            # Apply pagination
            query = query.limit(limit).offset(offset)

            # Execute query
            result = await self.db.execute(query)
            articles = result.unique().scalars().all()

            # Build response objects
            article_responses = []
            for article in articles:
                article_response = await self._build_article_response(article, current_user)
                article_responses.append(article_response)

            return article_responses, total_count
        except SQLAlchemyError as e:
            logger.error(f"Database error getting feed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve feed"
            ) from e

    async def create_article(
        self,
        article_data: ArticleCreate,
        author: User,
    ) -> ArticleResponse:
        """Create a new article.
        
        Args:
            article_data: The article creation data.
            author: The author of the article.
            
        Returns:
            An ArticleResponse for the created article.
            
        Raises:
            HTTPException: If article creation fails.
        """
        try:
            # Sanitize content to prevent XSS
            sanitized_title = self._sanitize_content(article_data.title)
            sanitized_description = self._sanitize_content(article_data.description)
            sanitized_body = self._sanitize_content(article_data.body)
            
            # Generate unique slug
            slug = await self._generate_unique_slug(sanitized_title)
            
            logger.info(f"Creating article with slug: {slug}")

            # Create article
            article = Article(
                slug=slug,
                title=sanitized_title,
                description=sanitized_description,
                body=sanitized_body,
                author_id=author.id,
            )
            self.db.add(article)
            await self.db.flush()

            # Add tags
            for tag_name in article_data.tagList:
                tag = await self._get_or_create_tag(tag_name)
                article.tags.append(tag)

            await self.db.commit()
            await self.db.refresh(article)

            # Load relationships
            await self.db.refresh(article, ["author", "tags"])
            
            logger.info(f"Successfully created article: {slug}")

            return await self._build_article_response(article, author)
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error creating article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create article"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create article"
            ) from e

    async def get_article_by_slug(
        self,
        slug: str,
        current_user: Optional[User] = None,
    ) -> Optional[ArticleResponse]:
        """Get a single article by slug.
        
        Args:
            slug: The article slug.
            current_user: The currently authenticated user (optional).
            
        Returns:
            An ArticleResponse if found, None otherwise.
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author),
                    selectinload(Article.tags),
                )
                .where(Article.slug == slug)
            )
            article = result.scalars().first()

            if not article:
                return None

            return await self._build_article_response(article, current_user)
        except SQLAlchemyError as e:
            logger.error(f"Database error getting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve article"
            ) from e

    async def update_article(
        self,
        slug: str,
        article_data: ArticleUpdate,
        current_user: User,
    ) -> ArticleResponse:
        """Update an existing article.
        
        Args:
            slug: The article slug.
            article_data: The article update data.
            current_user: The currently authenticated user.
            
        Returns:
            An ArticleResponse for the updated article.
            
        Raises:
            HTTPException: If article not found, user not authorized, or update fails.
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author),
                    selectinload(Article.tags),
                )
                .where(Article.slug == slug)
            )
            article = result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Check ownership
            if article.author_id != current_user.id:
                logger.warning(
                    f"Unauthorized update attempt on article {slug}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update this article",
                )

            # Update fields with sanitization
            if article_data.title is not None:
                sanitized_title = self._sanitize_content(article_data.title)
                article.title = sanitized_title
                # Regenerate slug if title changes
                article.slug = await self._generate_unique_slug(sanitized_title)
            
            if article_data.description is not None:
                article.description = self._sanitize_content(article_data.description)
            
            if article_data.body is not None:
                article.body = self._sanitize_content(article_data.body)

            await self.db.commit()
            await self.db.refresh(article)
            
            logger.info(f"Successfully updated article: {article.slug}")

            return await self._build_article_response(article, current_user)
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error updating article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update article"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error updating article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update article"
            ) from e

    async def delete_article(
        self,
        slug: str,
        current_user: User,
    ) -> None:
        """Delete an article.
        
        Args:
            slug: The article slug.
            current_user: The currently authenticated user.
            
        Raises:
            HTTPException: If article not found, user not authorized, or deletion fails.
        """
        try:
            result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Check ownership
            if article.author_id != current_user.id:
                logger.warning(
                    f"Unauthorized delete attempt on article {slug}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this article",
                )

            await self.db.delete(article)
            await self.db.commit()
            logger.info(f"Successfully deleted article: {slug}")
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error deleting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete article"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error deleting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete article"
            ) from e

    async def favorite_article(
        self,
        slug: str,
        current_user: User,
    ) -> ArticleResponse:
        """Favorite an article.
        
        Args:
            slug: The article slug.
            current_user: The currently authenticated user.
            
        Returns:
            An ArticleResponse for the favorited article.
            
        Raises:
            HTTPException: If article not found or favoriting fails.
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author),
                    selectinload(Article.tags),
                )
                .where(Article.slug == slug)
            )
            article = result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Check if already favorited
            is_favorited = await self._is_favorited(current_user.id, article.id)
            
            if not is_favorited:
                # Add to favorites
                await self.db.execute(
                    article_favorites.insert().values(
                        user_id=current_user.id,
                        article_id=article.id
                    )
                )
                await self.db.commit()
                logger.info(f"User favorited article: {slug}")

            return await self._build_article_response(article, current_user)
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error favoriting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to favorite article"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error favoriting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to favorite article"
            ) from e

    async def unfavorite_article(
        self,
        slug: str,
        current_user: User,
    ) -> ArticleResponse:
        """Unfavorite an article.
        
        Args:
            slug: The article slug.
            current_user: The currently authenticated user.
            
        Returns:
            An ArticleResponse for the unfavorited article.
            
        Raises:
            HTTPException: If article not found or unfavoriting fails.
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author),
                    selectinload(Article.tags),
                )
                .where(Article.slug == slug)
            )
            article = result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Check if favorited
            is_favorited = await self._is_favorited(current_user.id, article.id)
            
            if is_favorited:
                # Remove from favorites
                await self.db.execute(
                    article_favorites.delete().where(
                        and_(
                            article_favorites.c.user_id == current_user.id,
                            article_favorites.c.article_id == article.id
                        )
                    )
                )
                await self.db.commit()
                logger.info(f"User unfavorited article: {slug}")

            return await self._build_article_response(article, current_user)
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error unfavoriting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unfavorite article"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error unfavoriting article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unfavorite article"
            ) from e

    async def get_comments(
        self,
        slug: str,
        current_user: Optional[User] = None,
    ) -> List[CommentResponse]:
        """Get all comments for an article.
        
        Args:
            slug: The article slug.
            current_user: The currently authenticated user (optional).
            
        Returns:
            A list of CommentResponse objects.
            
        Raises:
            HTTPException: If article not found.
        """
        try:
            # First check if article exists
            article_result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = article_result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Get comments
            result = await self.db.execute(
                select(Comment)
                .options(selectinload(Comment.author))
                .where(Comment.article_id == article.id)
                .order_by(Comment.created_at.desc())
            )
            comments = result.scalars().all()

            comment_responses = []
            for comment in comments:
                comment_response = await self._build_comment_response(comment, current_user)
                comment_responses.append(comment_response)
            
            return comment_responses
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting comments: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve comments"
            ) from e

    async def create_comment(
        self,
        slug: str,
        comment_data: CommentCreate,
        author: User,
    ) -> CommentResponse:
        """Create a comment on an article.
        
        Args:
            slug: The article slug.
            comment_data: The comment creation data.
            author: The author of the comment.
            
        Returns:
            A CommentResponse for the created comment.
            
        Raises:
            HTTPException: If article not found or comment creation fails.
        """
        try:
            # Get article
            result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Sanitize comment body to prevent XSS
            sanitized_body = self._sanitize_content(comment_data.body)

            # Create comment
            comment = Comment(
                body=sanitized_body,
                article_id=article.id,
                author_id=author.id,
            )
            self.db.add(comment)
            await self.db.commit()
            await self.db.refresh(comment)

            # Load author relationship
            await self.db.refresh(comment, ["author"])
            
            logger.info(f"Created comment on article: {slug}")

            return await self._build_comment_response(comment, author)
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error creating comment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create comment"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating comment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create comment"
            ) from e

    async def delete_comment(
        self,
        slug: str,
        comment_id: int,
        current_user: User,
    ) -> None:
        """Delete a comment.
        
        Args:
            slug: The article slug.
            comment_id: The comment ID.
            current_user: The currently authenticated user.
            
        Raises:
            HTTPException: If article/comment not found, user not authorized, or deletion fails.
        """
        try:
            # First verify the article exists
            article_result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = article_result.scalars().first()

            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            # Get the comment
            result = await self.db.execute(
                select(Comment).where(Comment.id == comment_id)
            )
            comment = result.scalars().first()

            if not comment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Comment not found",
                )

            # Verify the comment belongs to the specified article
            if comment.article_id != article.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Comment not found for this article",
                )

            # Check ownership
            if comment.author_id != current_user.id:
                logger.warning(
                    f"Unauthorized delete attempt on comment {comment_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this comment",
                )

            await self.db.delete(comment)
            await self.db.commit()
            logger.info(f"Successfully deleted comment {comment_id} from article: {slug}")
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error deleting comment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete comment"
            ) from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error deleting comment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete comment"
            ) from e

    async def get_all_tags(self) -> List[str]:
        """Get all tags.
        
        Returns:
            A list of tag names.
        """
        try:
            result = await self.db.execute(select(Tag).order_by(Tag.tag))
            tags = result.scalars().all()
            return [tag.tag for tag in tags]
        except SQLAlchemyError as e:
            logger.error(f"Database error getting tags: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve tags"
            ) from e
