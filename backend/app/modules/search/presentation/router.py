"""GET /api/search?q=… (SDD mục 7.1): document_id, pages, snippets; lọc quyền; phân trang; khớp cả tên (v0.13).

FR-19 (v0.14): mặc định ẩn tài liệu hết hiệu lực (include_expired=true để hiện), lọc validity.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.modules.auth.presentation.deps import CurrentPrincipal, DbSession
from app.modules.categories.application.manage import names as category_names
from app.modules.search.application.search import search
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(prefix="/api/search", tags=["search"])


class PageHitOut(BaseModel):
    page_number: int
    snippet: str
    match_start: int
    match_end: int


class SearchHitOut(BaseModel):
    document_id: uuid.UUID
    title: str
    category_name: str | None
    pages: list[PageHitOut]
    title_match: bool = False
    validity_status: str = "unspecified"
    valid_until: date | None = None


@router.get("", response_model=Page[SearchHitOut])
def search_documents(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str, Query(max_length=200)] = "",
    category_id: int | None = None,
    status: Annotated[str | None, Query(pattern="^(queued|processing|completed|failed)$")] = None,
    include_expired: bool = False,
    validity: Annotated[str | None, Query(pattern="^(unspecified|effective|effective_until|expired)$")] = None,
) -> Page[SearchHitOut]:
    hits, total = search(
        db,
        principal,
        q,
        params,
        category_id=category_id,
        status=status,
        include_expired=include_expired,
        validity=validity,
    )
    cats = category_names(db, {h.category_id for h in hits})
    items = [
        SearchHitOut(
            document_id=h.document_id,
            title=h.title,
            category_name=cats.get(h.category_id),
            pages=[PageHitOut(**p.__dict__) for p in h.pages],
            title_match=h.title_match,
            validity_status=h.validity_status,
            valid_until=h.valid_until,
        )
        for h in hits
    ]
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)
