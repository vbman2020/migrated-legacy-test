import logging
import secrets
import string
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User

from .models import Article, Comment, Tag
from .schemas import (
    ArticleCreateSchema,
    ArticleSchema,
    ArticleUpdateSchema,
    CommentCreateSchema,
    CommentSchema,
    ProfileSchema,
)

logger = logging.getLogger(__name__)


def generate_random_string(length: int = 6) -> str:
    """
    Generate a random string for unique slug suffix.
    Uses secrets module for cryptographically strong randomness.
    
    Args:
        length: Length of the random string (default: 6)
    
    Returns:
        Random alphanumeric string in lowercase
    """
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_slug(title: str, max_length: int = 255) -> str:
    """
    Generate a unique slug from title with random suffix.
    
    Args:
        title: Article title to slugify
        max_length: Maximum length of the slug (default: 255)
    
    Returns:
        Slugified title with random suffix
    """
    # Sanitize and slugify the title
    base_slug = slugify(title, max_length=max_length - 7)  # Leave room for suffix
    
    if not base_slug:
        base_slug = "article"
    
    unique_suffix = generate_random_string()
    
    # Ensure the combined slug + suffix doesn't exceed max_length
    while len(base_slug + '-' + unique_suffix) > max_length:
        parts = base_slug.split('-')
        if len(parts) == 1:
            # No hyphens, truncate arbitrarily
            base_slug = base_slug[:max_length - len(unique_suffix) - 1]
        else:
            # Remove last part
            base_slug = '-'.join(parts[:-1])
    
    return f"{base_slug}-{unique_suffix}"


class ArticleService:
    """
    Service layer for article-related operations.
    Handles business logic for CRUD operations, favoriting, and feed generation.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_tags(self, tag_names: List[str]) -> List[Tag]:
        """
        Get or create tags by name with race condition handling.
        
        Args:
            tag_names: List of tag names to get or create
        
        Returns:
            List of Tag objects
        """
        if not tag_names:
            return []
        
        tags = []
        for tag_name in tag_names:
            # Sanitize tag name
            tag_name_clean = tag_name.strip()[:100]
            if not tag_name_clean:
                continue
                
            tag_slug = tag_name_clean.lower()
            try:
                # Try to find existing tag using parameterized query
                result = await self.db.execute(
                    select(Tag).where(Tag.slug == tag_slug)
                )
                tag = result.scalar_one_or_none()
                
                if not tag:
                    # Create new tag
                    tag = Tag(tag=tag_name_clean, slug=tag_slug)
                    self.db.add(tag)
                    try:
                        await self.db.flush()
                    except IntegrityError:
                        # Handle race condition where tag was created by another request
                        await self.db.rollback()
                        result = await self.db.execute(
                            select(Tag).where(Tag.slug == tag_slug)
                        )
                        tag = result.scalar_one_or_none()
                        if not tag:
                            # If still not found, log and skip this tag
                            logger.error(f"Failed to create or retrieve tag with slug: {tag_slug}")
                            continue
                
                tags.append(tag)
            except IntegrityError as e:
                # Log integrity errors without exposing details
                logger.error(f"IntegrityError while processing tag: {str(e)}")
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process tags"
                )
            except Exception as e:
                logger.error(f"Error processing tag: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process tags"
                )
        
        return tags

    def _is_favorited_by_user(self, article: Article, user: Optional[User]) -> bool:
        """
        Check if article is favorited by user.
        
        Args:
            article: Article to check
            user: User to check for (optional)
        
        Returns:
            True if favorited, False otherwise
        """
        if not user:
            return False
        return any(fav_user.id == user.id for fav_user in article.favorited_by)

    def _is_following_author(self, author: User, current_user: Optional[User]) -> bool:
        """
        Check if current user is following the author.
        
        Args:
            author: Author to check
            current_user: Current user (optional)
        
        Returns:
            True if following, False otherwise
        """
        if not current_user:
            return False
        return any(followed.id == author.id for followed in current_user.following)

    def _article_to_schema(self, article: Article, current_user: Optional[User]) -> ArticleSchema:
        """
        Convert Article model to ArticleSchema.
        
        Args:
            article: Article model instance
            current_user: Current user for favorited/following flags (optional)
        
        Returns:
            ArticleSchema instance
        """
        return ArticleSchema(
            slug=article.slug,
            title=article.title,
            description=article.description,
            body=article.body,
            tagList=[tag.tag for tag in article.tags],
            createdAt=article.created_at,
            updatedAt=article.updated_at,
            favorited=self._is_favorited_by_user(article, current_user),
            favoritesCount=len(article.favorited_by),
            author=ProfileSchema(
                username=article.author.username,
                bio=article.author.bio,
                image=article.author.image,
                following=self._is_following_author(article.author, current_user),
            ),
        )

    async def list_articles(
        self,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        current_user: Optional[User] = None,
    ) -> Tuple[List[ArticleSchema], int]:
        """
        List articles with optional filtering.
        
        Args:
            tag: Filter by tag name
            author: Filter by author username
            favorited: Filter by username who favorited
            limit: Number of articles to return
            offset: Number of articles to skip
            current_user: Current user for favorited/following flags
        
        Returns:
            Tuple of (list of ArticleSchema, total count)
        """
        try:
            # Build base query with relationships
            query = (
                select(Article)
                .options(
                    selectinload(Article.author).selectinload(User.following),
                    selectinload(Article.tags),
                    selectinload(Article.favorited_by),
                )
            )

            # Apply filters using parameterized queries
            if tag:
                query = query.join(Article.tags).where(Tag.tag == tag)
            
            if author:
                query = query.join(Article.author).where(User.username == author)
            
            if favorited:
                query = query.join(Article.favorited_by).where(User.username == favorited)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total_count = total_result.scalar_one()

            # Apply ordering, limit, and offset
            query = query.order_by(Article.created_at.desc()).limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            articles = result.scalars().unique().all()

            article_schemas = [
                self._article_to_schema(article, current_user) for article in articles
            ]

            return article_schemas, total_count
        except Exception as e:
            logger.error(f"Error listing articles: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve articles"
            )

    async def get_feed(
        self,
        current_user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ArticleSchema], int]:
        """
        Get articles from followed users (feed).
        
        Args:
            current_user: Current authenticated user
            limit: Number of articles to return
            offset: Number of articles to skip
        
        Returns:
            Tuple of (list of ArticleSchema, total count)
        """
        try:
            # Get list of followed user IDs
            followed_ids = [user.id for user in current_user.following]
            
            if not followed_ids:
                return [], 0

            # Build query for articles by followed users
            query = (
                select(Article)
                .options(
                    selectinload(Article.author).selectinload(User.following),
                    selectinload(Article.tags),
                    selectinload(Article.favorited_by),
                )
                .where(Article.author_id.in_(followed_ids))
            )

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total_count = total_result.scalar_one()

            # Apply ordering, limit, and offset
            query = query.order_by(Article.created_at.desc()).limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            articles = result.scalars().all()

            article_schemas = [
                self._article_to_schema(article, current_user) for article in articles
            ]

            return article_schemas, total_count
        except Exception as e:
            logger.error(f"Error retrieving feed for user {current_user.id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve feed"
            )

    async def create_article(
        self,
        article_data: ArticleCreateSchema,
        author: User,
    ) -> ArticleSchema:
        """
        Create a new article.
        
        Args:
            article_data: Article creation data
            author: Article author
        
        Returns:
            Created ArticleSchema
        """
        try:
            # Generate unique slug with retry logic
            max_retries = 10
            slug = None
            for attempt in range(max_retries):
                candidate_slug = generate_slug(article_data.title)
                # Check if slug exists
                result = await self.db.execute(
                    select(Article).where(Article.slug == candidate_slug)
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    slug = candidate_slug
                    break
            
            if not slug:
                logger.error(f"Failed to generate unique slug after {max_retries} attempts")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate unique slug"
                )
            
            # Get or create tags
            tags = await self._get_or_create_tags(article_data.tagList or [])
            
            # Create article
            article = Article(
                slug=slug,
                title=article_data.title,
                description=article_data.description,
                body=article_data.body,
                author_id=author.id,
                tags=tags,
            )
            
            self.db.add(article)
            await self.db.commit()
            await self.db.refresh(article)
            
            # Load relationships
            await self.db.refresh(article, ["author", "tags", "favorited_by"])
            # Load author's following for profile
            await self.db.refresh(article.author, ["following"])
            
            logger.info(f"Article created: {article.slug} by user {author.id}")
            return self._article_to_schema(article, author)
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating article: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create article"
            )

    async def get_article_by_slug(
        self,
        slug: str,
        current_user: Optional[User] = None,
    ) -> Optional[ArticleSchema]:
        """
        Get an article by slug.
        
        Args:
            slug: Article slug
            current_user: Current user for favorited/following flags
        
        Returns:
            ArticleSchema if found, None otherwise
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author).selectinload(User.following),
                    selectinload(Article.tags),
                    selectinload(Article.favorited_by),
                )
                .where(Article.slug == slug)
            )
            article = result.scalar_one_or_none()
            
            if not article:
                return None
            
            return self._article_to_schema(article, current_user)
        except Exception as e:
            logger.error(f"Error retrieving article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve article"
            )

    async def update_article(
        self,
        slug: str,
        article_data: ArticleUpdateSchema,
        current_user: User,
    ) -> ArticleSchema:
        """
        Update an article.
        
        Args:
            slug: Article slug
            article_data: Article update data
            current_user: Current user (must be author)
        
        Returns:
            Updated ArticleSchema
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author).selectinload(User.following),
                    selectinload(Article.tags),
                    selectinload(Article.favorited_by),
                )
                .where(Article.slug == slug)
            )
            article = result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Check ownership
            if article.author_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not allowed to update this article.",
                )
            
            # Update fields
            if article_data.title is not None:
                article.title = article_data.title
                # Regenerate slug if title changed with retry logic
                max_retries = 10
                new_slug = None
                for attempt in range(max_retries):
                    candidate_slug = generate_slug(article_data.title)
                    if candidate_slug == article.slug:
                        new_slug = candidate_slug
                        break
                    # Check if slug exists
                    result = await self.db.execute(
                        select(Article).where(Article.slug == candidate_slug)
                    )
                    existing = result.scalar_one_or_none()
                    if not existing:
                        new_slug = candidate_slug
                        break
                
                if not new_slug:
                    logger.error(f"Failed to generate unique slug after {max_retries} attempts")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to generate unique slug"
                    )
                article.slug = new_slug
            
            if article_data.description is not None:
                article.description = article_data.description
            
            if article_data.body is not None:
                article.body = article_data.body
            
            if article_data.tagList is not None:
                tags = await self._get_or_create_tags(article_data.tagList)
                article.tags = tags
            
            await self.db.commit()
            await self.db.refresh(article)
            await self.db.refresh(article, ["author", "tags", "favorited_by"])
            await self.db.refresh(article.author, ["following"])
            
            logger.info(f"Article updated: {article.slug} by user {current_user.id}")
            return self._article_to_schema(article, current_user)
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update article"
            )

    async def delete_article(
        self,
        slug: str,
        current_user: User,
    ) -> None:
        """
        Delete an article.
        
        Args:
            slug: Article slug
            current_user: Current user (must be author)
        """
        try:
            result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Check ownership
            if article.author_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not allowed to delete this article.",
                )
            
            await self.db.delete(article)
            await self.db.commit()
            
            logger.info(f"Article deleted: {slug} by user {current_user.id}")
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete article"
            )

    async def favorite_article(
        self,
        slug: str,
        current_user: User,
    ) -> ArticleSchema:
        """
        Favorite an article.
        
        Args:
            slug: Article slug
            current_user: Current user
        
        Returns:
            Updated ArticleSchema
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author).selectinload(User.following),
                    selectinload(Article.tags),
                    selectinload(Article.favorited_by),
                )
                .where(Article.slug == slug)
            )
            article = result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Check if already favorited
            if not self._is_favorited_by_user(article, current_user):
                article.favorited_by.append(current_user)
                await self.db.commit()
                await self.db.refresh(article)
                await self.db.refresh(article, ["author", "tags", "favorited_by"])
                await self.db.refresh(article.author, ["following"])
                logger.info(f"Article favorited: {slug} by user {current_user.id}")
            
            return self._article_to_schema(article, current_user)
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error favoriting article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to favorite article"
            )

    async def unfavorite_article(
        self,
        slug: str,
        current_user: User,
    ) -> ArticleSchema:
        """
        Unfavorite an article.
        
        Args:
            slug: Article slug
            current_user: Current user
        
        Returns:
            Updated ArticleSchema
        """
        try:
            result = await self.db.execute(
                select(Article)
                .options(
                    selectinload(Article.author).selectinload(User.following),
                    selectinload(Article.tags),
                    selectinload(Article.favorited_by),
                )
                .where(Article.slug == slug)
            )
            article = result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Check if favorited
            if self._is_favorited_by_user(article, current_user):
                article.favorited_by = [
                    user for user in article.favorited_by if user.id != current_user.id
                ]
                await self.db.commit()
                await self.db.refresh(article)
                await self.db.refresh(article, ["author", "tags", "favorited_by"])
                await self.db.refresh(article.author, ["following"])
                logger.info(f"Article unfavorited: {slug} by user {current_user.id}")
            
            return self._article_to_schema(article, current_user)
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error unfavoriting article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unfavorite article"
            )


class CommentService:
    """
    Service layer for comment-related operations.
    Handles business logic for adding, retrieving, and deleting comments.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    def _is_following_author(self, author: User, current_user: Optional[User]) -> bool:
        """
        Check if current user is following the author.
        
        Args:
            author: Author to check
            current_user: Current user (optional)
        
        Returns:
            True if following, False otherwise
        """
        if not current_user:
            return False
        return any(followed.id == author.id for followed in current_user.following)

    def _comment_to_schema(self, comment: Comment, current_user: Optional[User]) -> CommentSchema:
        """
        Convert Comment model to CommentSchema.
        
        Args:
            comment: Comment model instance
            current_user: Current user for following flag (optional)
        
        Returns:
            CommentSchema instance
        """
        return CommentSchema(
            id=comment.id,
            createdAt=comment.created_at,
            updatedAt=comment.updated_at,
            body=comment.body,
            author=ProfileSchema(
                username=comment.author.username,
                bio=comment.author.bio,
                image=comment.author.image,
                following=self._is_following_author(comment.author, current_user),
            ),
        )

    async def get_comments_for_article(
        self,
        slug: str,
        current_user: Optional[User] = None,
    ) -> List[CommentSchema]:
        """
        Get all comments for an article.
        
        Args:
            slug: Article slug
            current_user: Current user for following flags
        
        Returns:
            List of CommentSchema
        """
        try:
            # First, get the article
            article_result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = article_result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Get comments
            result = await self.db.execute(
                select(Comment)
                .options(
                    selectinload(Comment.author).selectinload(User.following),
                )
                .where(Comment.article_id == article.id)
                .order_by(Comment.created_at.desc())
            )
            comments = result.scalars().all()
            
            return [self._comment_to_schema(comment, current_user) for comment in comments]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving comments for article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve comments"
            )

    async def add_comment(
        self,
        slug: str,
        comment_data: CommentCreateSchema,
        author: User,
    ) -> CommentSchema:
        """
        Add a comment to an article.
        
        Args:
            slug: Article slug
            comment_data: Comment creation data
            author: Comment author
        
        Returns:
            Created CommentSchema
        """
        try:
            # First, get the article
            article_result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = article_result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Create comment
            comment = Comment(
                body=comment_data.body,
                article_id=article.id,
                author_id=author.id,
            )
            
            self.db.add(comment)
            await self.db.commit()
            await self.db.refresh(comment)
            await self.db.refresh(comment, ["author"])
            await self.db.refresh(comment.author, ["following"])
            
            logger.info(f"Comment added to article {slug} by user {author.id}")
            return self._comment_to_schema(comment, author)
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adding comment to article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add comment"
            )

    async def delete_comment(
        self,
        slug: str,
        comment_id: int,
        current_user: User,
    ) -> None:
        """
        Delete a comment.
        
        Args:
            slug: Article slug
            comment_id: Comment ID
            current_user: Current user (must be author)
        """
        try:
            # First, verify the article exists
            article_result = await self.db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = article_result.scalar_one_or_none()
            
            if not article:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="An article with this slug does not exist.",
                )
            
            # Get the comment and verify it belongs to the article
            result = await self.db.execute(
                select(Comment)
                .where(Comment.id == comment_id)
                .where(Comment.article_id == article.id)
            )
            comment = result.scalar_one_or_none()
            
            if not comment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="A comment with this ID does not exist for this article.",
                )
            
            # Check ownership
            if comment.author_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not allowed to delete this comment.",
                )
            
            await self.db.delete(comment)
            await self.db.commit()
            
            logger.info(f"Comment {comment_id} deleted from article {slug} by user {current_user.id}")
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting comment {comment_id} from article {slug}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete comment"
            )


class TagService:
    """
    Service layer for tag-related operations.
    Handles business logic for retrieving tags.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_tags(self) -> List[str]:
        """
        Get list of all tags.
        
        Returns:
            List of tag names
        """
        try:
            result = await self.db.execute(
                select(Tag).order_by(Tag.tag)
            )
            tags = result.scalars().all()
            
            return [tag.tag for tag in tags]
        except Exception as e:
            logger.error(f"Error retrieving tags: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve tags"
            )
