"""Phân trang chuẩn (SDD mục 13): {items, total, page, page_size}. Dependency FastAPI ở app.shared.http."""

from dataclasses import dataclass

from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
