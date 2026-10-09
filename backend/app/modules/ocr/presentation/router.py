"""API ocr (SDD mục 7.1):
GET /api/documents/{id}/pages/{page}             raw_text, effective_text, confidence, boxes, version
PUT /api/documents/{id}/pages/{page}/correction  corrected_text + base_version -> version mới; 409 nếu lệch
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession
from app.modules.ocr.application import editor

router = APIRouter(prefix="/api/documents", tags=["ocr"])
PageNo = Annotated[int, Path(ge=1)]
MAX_TEXT = 200_000


class BoxOut(BaseModel):
    text: str
    score: float | None
    box: list[int] = Field(description="x, y, w, h theo pixel ảnh trang")


class PageOut(BaseModel):
    document_id: uuid.UUID
    page_number: int
    total_pages: int
    width: int
    height: int
    ocr_status: str
    engine_version: str | None
    is_text_layer: bool
    confidence: Decimal | None = Field(description="Điểm tin cậy model tự đánh giá (0-100), không phải accuracy")
    raw_text: str
    effective_text: str
    version: int = Field(description="Version hiện hành, gửi lại làm base_version khi lưu; 0 = chưa sửa")
    edited_by: uuid.UUID | None
    edited_at: datetime | None
    boxes: list[BoxOut]
    can_edit: bool


class CorrectionIn(BaseModel):
    corrected_text: str = Field(max_length=MAX_TEXT)
    base_version: int = Field(ge=0)


class CorrectionOut(BaseModel):
    version: int
    base_version: int
    edited_by: uuid.UUID | None
    edited_at: datetime


def page_out(d: Any) -> PageOut:
    return PageOut(**{**d.__dict__, "boxes": [BoxOut(**b) for b in d.boxes]})


@router.get("/{document_id}/pages/{page_number}", response_model=PageOut)
def get_page(document_id: uuid.UUID, page_number: PageNo, db: DbSession, principal: CurrentPrincipal) -> PageOut:
    return page_out(editor.get_page_detail(db, principal, document_id, page_number))


@router.put("/{document_id}/pages/{page_number}/correction", response_model=CorrectionOut)
def save_correction(
    document_id: uuid.UUID,
    page_number: PageNo,
    data: CorrectionIn,
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
) -> CorrectionOut:
    c = editor.save_correction(
        db,
        principal,
        document_id,
        page_number,
        corrected_text=data.corrected_text,
        base_version=data.base_version,
        ctx=ctx,
    )
    return CorrectionOut(version=c.version, base_version=c.base_version, edited_by=c.edited_by, edited_at=c.edited_at)
