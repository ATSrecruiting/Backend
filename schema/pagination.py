from fastapi import Query
from typing import List, Generic, TypeVar, Sequence
from pydantic import BaseModel, Field
from math import ceil


T = TypeVar("T")


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(
            10, ge=1, le=100, description="Number of items per page"
        ),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size

    def paginate(self, items: Sequence[T]) -> dict:
        """Paginate a sequence of items and return pagination metadata"""
        total_items = len(items)
        total_pages = ceil(total_items / self.page_size) if total_items > 0 else 0

        # Get paginated results
        start = self.offset
        end = start + self.page_size
        paginated_items = items[start:end]

        # Create response with metadata
        return {
            "items": paginated_items,
            "pagination": {
                "page": self.page,
                "page_size": self.page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_previous": self.page > 1,
                "has_next": self.page < total_pages,
                "previous_page": self.page - 1 if self.page > 1 else None,
                "next_page": self.page + 1 if self.page < total_pages else None,
            },
        }


# Generic pagination response model
class PaginatedResponse(Generic[T], BaseModel):
    items: List[T]
    pagination: dict = Field(...)
