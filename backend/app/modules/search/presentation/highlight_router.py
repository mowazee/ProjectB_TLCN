"""API highlight (SDD 7.2, P2-02):
GET /api/documents/{id}/pages/{page}/highlights?q=…   box {x, y, w, h} theo tọa độ ảnh trang;
rỗng kèm reason (empty_query | no_ocr | no_boxes | text_modified | not_found).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import CurrentPrincipal, DbSession, require_feature
from app.modules.search.application.highlight import page_highlights

router = APIRouter(prefix="/api/documents", tags=["highlight"], dependencies=[Depends(require_feature("highlight"))])


class HighlightBoxOut(BaseModel):
    x: int
    y: int
    w: int
    h: int
    line: int


class HighlightsOut(BaseModel):
    page_number: int
    width: int = Field(description="Kích thước ảnh trang (pixel) để React co giãn khung")
    height: int
    total: int
    boxes: list[HighlightBoxOut]
    reason: str | None = Field(description="Lý do khi không có khung nào")


@router.get("/{document_id}/pages/{page_number}/highlights", response_model=HighlightsOut)
def get_highlights(
    document_id: uuid.UUID,
    page_number: Annotated[int, Path(ge=1)],
    db: DbSession,
    principal: CurrentPrincipal,
    q: Annotated[str, Query(max_length=200)] = "",
) -> HighlightsOut:
    h = page_highlights(db, principal, document_id, page_number, q)
    return HighlightsOut(
        page_number=h.page_number,
        width=h.width,
        height=h.height,
        total=len(h.boxes),
        boxes=[HighlightBoxOut(x=b.x, y=b.y, w=b.w, h=b.h, line=b.line) for b in h.boxes],
        reason=h.reason,
    )
