import secrets
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from slugify import slugify

from sqlalchemy import select, func, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.articles.models import Article, Comment, Tag, article_favorites
from app.articles.schemas import ArticleCreate, ArticleUpdate, CommentCreate, ArticleResponse, CommentResponse
from app.auth.models import User
from app.profiles.schemas import ProfileResponse


def generate_random_string(length: int = 8) -> str:
    """Generate a random string for unique slug suffixes using token_hex for predictable length."""
    return secrets.token_hex(length // 2)[:length].lower()


async def generate_unique_slug(db: AsyncSession, title: str, max_length: int = 255, max_retries: int = 10) -> str:
    """Generate a unique slug from a title with collision retry logic."""
    base_slug = slugify(title)
    
    if len(base_slug) > max_length:
        base_slug = base_slug[:max_length]
    
    for attempt in range(max_retries):
        unique = generate_random_string()
        
        # Calculate available space for base slug
        while len(base_slug + '-' + unique) > max_length:
            parts = base_slug.split('-')
            if len(parts) == 1:
                # No hyphens, remove characters from the end
                base_slug = base_slug[:max_length - len(unique) - 1]
            else:
                base_slug = '-'.join(parts[:-1])
        
        slug = base_slug + '-' + unique
        
        # Check if slug exists
        result = await db.execute(
            select(Article.id).where(Article.slug == slug)
        )
        if result.scalar_one_or_none() is None:
            return slug
    
    # If we exhausted retries, raise an error
    raise ValueError(f"Unable to generate unique slug after {max_retries} attempts")


async def get_or_create_tags(db: AsyncSession, tag_names: List[str]) -> List[Tag]:
    """Get existing tags or create new ones."""
    tags = []
    for tag_name in tag_names:
        tag_slug = slugify(tag_name)
        
        # Try to get existing tag by slug
        result = await db.execute(
            select(Tag).where(Tag.slug == tag_slug)
        )
        tag = result.scalar_one_or_none()
        
        if not tag:
            # Create new tag
            tag = Tag(tag=tag_name, slug=tag_slug)
            db.add(tag)
            try:
                await db.flush()
            except IntegrityError:
                # Handle race condition - tag was created by another request
                await db.rollback()
                result = await db.execute(
                    select(Tag).where(Tag.slug == tag_slug)
                )
                tag = result.scalar_one_or_none()
                if not tag:
                    raise
        
        tags.append(tag)
    
    return tags


async def get_articles(
    db: AsyncSession,
    tag: Optional[str] = None,
    author: Optional[str] = None,
    favorited: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: Optional[User] = None,
) -> Tuple[List[Article], int]:
    """Get articles with optional filtering."""
    query = select(Article).options(
        joinedload(Article.author),
        selectinload(Article.tags),
        selectinload(Article.favorited_by),
    )
    
    # Apply filters
    if author:
        query = query.join(Article.author).where(User.username == author)
    
    if tag:
        tag_slug = slugify(tag)
        query = query.join(Article.tags).where(Tag.slug == tag_slug)
    
    if favorited:
        query = query.join(Article.favorited_by).where(User.username == favorited)
    
    # Get total count - use a more efficient count query
    count_query = select(func.count(Article.id))
    if author:
        count_query = count_query.select_from(Article).join(Article.author).where(User.username == author)
    elif tag:
        tag_slug = slugify(tag)
        count_query = count_query.select_from(Article).join(Article.tags).where(Tag.slug == tag_slug)
    elif favorited:
        count_query = count_query.select_from(Article).join(Article.favorited_by).where(User.username == favorited)
    else:
        count_query = count_query.select_from(Article)
    
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()
    
    # Apply pagination and ordering
    query = query.order_by(Article.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    articles = result.unique().scalars().all()
    
    return list(articles), total_count


async def get_feed(
    db: AsyncSession,
    user: User,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Article], int]:
    """Get articles from followed users."""
    # Get the list of followed user IDs
    from app.profiles.models import followers_association
    
    followed_ids_query = select(followers_association.c.followed_id).where(
        followers_association.c.follower_id == user.id
    )
    
    query = select(Article).options(
        joinedload(Article.author),
        selectinload(Article.tags),
        selectinload(Article.favorited_by),
    ).where(Article.author_id.in_(followed_ids_query))
    
    # Get total count - more efficient query
    count_query = select(func.count(Article.id)).where(Article.author_id.in_(followed_ids_query))
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()
    
    # Apply pagination and ordering
    query = query.order_by(Article.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    articles = result.unique().scalars().all()
    
    return list(articles), total_count


async def create_article(
    db: AsyncSession,
    article_data: ArticleCreate,
    author: User,
) -> Article:
    """Create a new article."""
    # Generate unique slug
    slug = await generate_unique_slug(db, article_data.title)
    
    # Create article
    article = Article(
        slug=slug,
        title=article_data.title,
        description=article_data.description,
        body=article_data.body,
        author_id=author.id,
    )
    
    db.add(article)
    await db.flush()
    
    # Add tags
    if article_data.tag_list:
        tags = await get_or_create_tags(db, article_data.tag_list)
        article.tags = tags
    
    await db.commit()
    await db.refresh(article)
    
    return article


async def get_article_by_slug(db: AsyncSession, slug: str) -> Optional[Article]:
    """Get an article by slug."""
    result = await db.execute(
        select(Article)
        .options(
            joinedload(Article.author),
            selectinload(Article.tags),
            selectinload(Article.favorited_by),
        )
        .where(Article.slug == slug)
    )
    return result.unique().scalar_one_or_none()


async def update_article(
    db: AsyncSession,
    article: Article,
    article_data: ArticleUpdate,
) -> Article:
    """Update an article. Keeps original slug to avoid breaking links."""
    update_data = article_data.model_dump(exclude_unset=True, by_alias=False)
    
    # Handle tag updates separately
    tag_list = update_data.pop('tag_list', None)
    
    # Update fields but keep original slug even if title changes
    for key, value in update_data.items():
        setattr(article, key, value)
    
    # Update tags if provided
    if tag_list is not None:
        tags = await get_or_create_tags(db, tag_list)
        article.tags = tags
    
    article.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(article)
    
    return article


async def delete_article(db: AsyncSession, article: Article) -> None:
    """Delete an article. Comments are cascade deleted automatically."""
    await db.delete(article)
    await db.commit()


async def favorite_article(db: AsyncSession, article: Article, user: User) -> None:
    """Favorite an article using direct INSERT to avoid race conditions."""
    # Use INSERT IGNORE pattern to handle concurrent favorites
    try:
        stmt = insert(article_favorites).values(
            article_id=article.id,
            user_id=user.id,
        )
        await db.execute(stmt)
        await db.commit()
    except IntegrityError:
        # Already favorited, rollback and continue
        await db.rollback()


async def unfavorite_article(db: AsyncSession, article: Article, user: User) -> None:
    """Unfavorite an article using direct DELETE to avoid race conditions."""
    stmt = delete(article_favorites).where(
        article_favorites.c.article_id == article.id,
        article_favorites.c.user_id == user.id,
    )
    await db.execute(stmt)
    await db.commit()


async def get_comments_for_article(db: AsyncSession, article_id: int) -> List[Comment]:
    """Get all comments for an article."""
    result = await db.execute(
        select(Comment)
        .options(joinedload(Comment.author))
        .where(Comment.article_id == article_id)
        .order_by(Comment.created_at.desc())
    )
    return list(result.unique().scalars().all())


async def create_comment(
    db: AsyncSession,
    article: Article,
    comment_data: CommentCreate,
    author: User,
) -> Comment:
    """Create a comment on an article."""
    comment = Comment(
        body=comment_data.body,
        article_id=article.id,
        author_id=author.id,
    )
    
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    return comment


async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Optional[Comment]:
    """Get a comment by ID."""
    result = await db.execute(
        select(Comment)
        .options(joinedload(Comment.author))
        .where(Comment.id == comment_id)
    )
    return result.unique().scalar_one_or_none()


async def delete_comment(db: AsyncSession, comment: Comment) -> None:
    """Delete a comment."""
    await db.delete(comment)
    await db.commit()


async def get_all_tags(db: AsyncSession) -> List[str]:
    """Get all unique tags."""
    result = await db.execute(select(Tag.tag).order_by(Tag.tag))
    return list(result.scalars().all())


async def is_article_favorited_by_user(
    db: AsyncSession,
    article_id: int,
    user_id: Optional[int],
) -> bool:
    """Check if an article is favorited by a user using efficient database query."""
    if not user_id:
        return False
    
    result = await db.execute(
        select(func.count())
        .select_from(article_favorites)
        .where(
            article_favorites.c.article_id == article_id,
            article_favorites.c.user_id == user_id,
        )
    )
    count = result.scalar_one()
    return count > 0


async def get_favorites_count(db: AsyncSession, article_id: int) -> int:
    """Get the count of favorites for an article using efficient database query."""
    result = await db.execute(
        select(func.count())
        .select_from(article_favorites)
        .where(article_favorites.c.article_id == article_id)
    )
    return result.scalar_one()


async def is_user_following(
    db: AsyncSession,
    current_user_id: Optional[int],
    profile_user_id: int,
) -> bool:
    """Check if current user is following the profile user."""
    if not current_user_id or current_user_id == profile_user_id:
        return False
    
    from app.profiles.models import followers_association
    
    result = await db.execute(
        select(func.count())
        .select_from(followers_association)
        .where(
            followers_association.c.follower_id == current_user_id,
            followers_association.c.followed_id == profile_user_id,
        )
    )
    count = result.scalar_one()
    return count > 0


async def article_to_response(
    article: Article,
    current_user: Optional[User],
    db: AsyncSession,
) -> ArticleResponse:
    """Convert an Article model to ArticleResponse schema."""
    current_user_id = current_user.id if current_user else None
    
    favorited = await is_article_favorited_by_user(db, article.id, current_user_id)
    favorites_count = await get_favorites_count(db, article.id)
    following = await is_user_following(db, current_user_id, article.author_id)
    
    return ArticleResponse(
        slug=article.slug,
        title=article.title,
        description=article.description,
        body=article.body,
        tag_list=[tag.tag for tag in article.tags],
        created_at=article.created_at,
        updated_at=article.updated_at,
        favorited=favorited,
        favorites_count=favorites_count,
        author=ProfileResponse(
            username=article.author.username,
            bio=article.author.bio or "",
            image=article.author.image or "",
            following=following,
        ),
    )


async def articles_to_response_batch(
    articles: List[Article],
    current_user: Optional[User],
    db: AsyncSession,
) -> List[ArticleResponse]:
    """Batch convert articles to responses for better performance."""
    if not articles:
        return []
    
    current_user_id = current_user.id if current_user else None
    article_ids = [article.id for article in articles]
    author_ids = [article.author_id for article in articles]
    
    # Batch query for favorites
    favorites_dict = {}
    if current_user_id:
        result = await db.execute(
            select(article_favorites.c.article_id)
            .where(
                article_favorites.c.article_id.in_(article_ids),
                article_favorites.c.user_id == current_user_id,
            )
        )
        favorited_article_ids = set(result.scalars().all())
        favorites_dict = {aid: aid in favorited_article_ids for aid in article_ids}
    else:
        favorites_dict = {aid: False for aid in article_ids}
    
    # Batch query for favorites counts
    result = await db.execute(
        select(article_favorites.c.article_id, func.count())
        .where(article_favorites.c.article_id.in_(article_ids))
        .group_by(article_favorites.c.article_id)
    )
    favorites_counts = dict(result.all())
    
    # Batch query for following relationships
    following_dict = {}
    if current_user_id:
        from app.profiles.models import followers_association
        result = await db.execute(
            select(followers_association.c.followed_id)
            .where(
                followers_association.c.follower_id == current_user_id,
                followers_association.c.followed_id.in_(author_ids),
            )
        )
        followed_ids = set(result.scalars().all())
        following_dict = {aid: aid in followed_ids for aid in author_ids}
    else:
        following_dict = {aid: False for aid in author_ids}
    
    # Build responses
    responses = []
    for article in articles:
        responses.append(
            ArticleResponse(
                slug=article.slug,
                title=article.title,
                description=article.description,
                body=article.body,
                tag_list=[tag.tag for tag in article.tags],
                created_at=article.created_at,
                updated_at=article.updated_at,
                favorited=favorites_dict.get(article.id, False),
                favorites_count=favorites_counts.get(article.id, 0),
                author=ProfileResponse(
                    username=article.author.username,
                    bio=article.author.bio or "",
                    image=article.author.image or "",
                    following=following_dict.get(article.author_id, False),
                ),
            )
        )
    
    return responses


async def comment_to_response(
    comment: Comment,
    current_user: Optional[User],
    db: AsyncSession,
) -> CommentResponse:
    """Convert a Comment model to CommentResponse schema."""
    current_user_id = current_user.id if current_user else None
    following = await is_user_following(db, current_user_id, comment.author_id)
    
    return CommentResponse(
        id=comment.id,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=ProfileResponse(
            username=comment.author.username,
            bio=comment.author.bio or "",
            image=comment.author.image or "",
            following=following,
        ),
    )


async def comments_to_response_batch(
    comments: List[Comment],
    current_user: Optional[User],
    db: AsyncSession,
) -> List[CommentResponse]:
    """Batch convert comments to responses for better performance."""
    if not comments:
        return []
    
    current_user_id = current_user.id if current_user else None
    author_ids = [comment.author_id for comment in comments]
    
    # Batch query for following relationships
    following_dict = {}
    if current_user_id:
        from app.profiles.models import followers_association
        result = await db.execute(
            select(followers_association.c.followed_id)
            .where(
                followers_association.c.follower_id == current_user_id,
                followers_association.c.followed_id.in_(author_ids),
            )
        )
        followed_ids = set(result.scalars().all())
        following_dict = {aid: aid in followed_ids for aid in author_ids}
    else:
        following_dict = {aid: False for aid in author_ids}
    
    # Build responses
    responses = []
    for comment in comments:
        responses.append(
            CommentResponse(
                id=comment.id,
                body=comment.body,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                author=ProfileResponse(
                    username=comment.author.username,
                    bio=comment.author.bio or "",
                    image=comment.author.image or "",
                    following=following_dict.get(comment.author_id, False),
                ),
            )
        )
    
    return responses
