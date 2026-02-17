from typing import Generic, List, TypeVar, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    limit: int = Field(default=20, ge=1, le=100, description="Number of items to return")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class Page(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    limit: int
    offset: int
    
    @property
    def has_next(self) -> bool:
        """Check if there are more items."""
        return self.offset + self.limit < self.total
    
    @property
    def has_previous(self) -> bool:
        """Check if there are previous items."""
        return self.offset > 0


async def paginate(
    db: AsyncSession,
    query,
    limit: int = 20,
    offset: int = 0,
) -> Page:
    """Paginate a SQLAlchemy query.
    
    Args:
        db: Database session
        query: SQLAlchemy select query
        limit: Maximum number of items to return
        offset: Number of items to skip
    
    Returns:
        Page object with items and pagination metadata
    """
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Apply pagination
    paginated_query = query.limit(limit).offset(offset)
    result = await db.execute(paginated_query)
    items = result.scalars().all()
    
    return Page(
        items=list(items),
        total=total,
        limit=limit,
        offset=offset,
    )


def get_pagination_params(
    limit: Optional[int] = 20,
    offset: Optional[int] = 0,
) -> PaginationParams:
    """Dependency for extracting pagination parameters from request."""
    return PaginationParams(limit=limit or 20, offset=offset or 0)
