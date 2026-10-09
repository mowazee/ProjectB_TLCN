"""API classification (SDD 7.2, P2-05):
GET  /api/documents/{id}/category-suggestions          tối đa 3 gợi ý kèm điểm (chỉ danh mục đang dùng)
POST /api/documents/{id}/category-suggestions/accept   {category_id} -> cập nhật category_id; audit
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.classification.application import suggest

router = APIRouter(
    prefix="/api/documents", tags=["classification"], dependencies=[Depends(require_feature("classification"))]
)


class SuggestionOut(BaseModel):
    category_id: int
    name: str
    score: float = Field(description="Độ tương đồng cosine 0-1 (điểm mô hình, không phải xác suất đúng)")
    is_current: bool


class SuggestionsOut(BaseModel):
    items: list[SuggestionOut]
    job_id: uuid.UUID | None
    job_status: str | None


class AcceptIn(BaseModel):
    category_id: int


@router.get("/{document_id}/category-suggestions", response_model=SuggestionsOut)
def get_suggestions(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> SuggestionsOut:
    items, job = suggest.get_suggestions(db, principal, document_id)
    return SuggestionsOut(
        items=[SuggestionOut(**s.__dict__) for s in items],
        job_id=job.id if job else None,
        job_status=str(job.status) if job else None,
    )


@router.post("/{document_id}/category-suggestions/accept", response_model=SuggestionOut)
def accept(
    document_id: uuid.UUID, data: AcceptIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> SuggestionOut:
    return SuggestionOut(**suggest.accept(db, principal, document_id, data.category_id, ctx).__dict__)
