"""API workflow (SDD 7.2, P2-01):
POST /api/documents/{id}/approval/{action}   action ∈ submit, approve, reject, publish, unpublish; sai trạng thái 409
GET  /api/documents/{id}/approval            trạng thái hiện tại + action được phép (cho React hiện nút)
GET  /api/documents/{id}/approvals           lịch sử duyệt
GET  /api/reviews                            hàng chờ duyệt (Kiểm duyệt/Admin); FR-19 ẩn hết hiệu lực
POST /api/reviews/bulk                       FR-20: duyệt/xuất bản/từ chối hàng loạt (≤ 20)
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.workflow.application import approvals
from app.modules.workflow.domain.state_machine import Action
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(tags=["workflow"], dependencies=[Depends(require_feature("workflow"))])


class ApprovalIn(BaseModel):
    comments: str | None = Field(default=None, max_length=2000, description="Bắt buộc khi reject")
    has_physical_copy: bool | None = Field(
        default=None, description="submit khi bật borrowing (D-12): tài liệu có bản cứng không"
    )
    storage_location_id: int | None = Field(default=None, description="submit, has_physical_copy=true: kho/kệ")
    validity_status: str | None = Field(
        default=None,
        description="FR-19: submit (bắt buộc), approve (tùy chọn): unspecified | effective | effective_until | expired",
    )
    valid_until: date | None = Field(default=None, description="FR-19: bắt buộc khi effective_until, ≥ hôm nay")


PAYLOAD_FIELDS = {"has_physical_copy", "storage_location_id", "validity_status", "valid_until"}


class ApprovalStateOut(BaseModel):
    approval_status: str
    allowed_actions: list[str]


class ApprovalEntryOut(BaseModel):
    id: uuid.UUID
    action: str
    comments: str | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    created_at: datetime


class ReviewItemOut(BaseModel):
    document_id: uuid.UUID
    title: str
    category_id: int
    submitted_by: str | None
    submitted_at: datetime | None
    validity_status: str = "unspecified"
    valid_until: date | None = None


@router.post("/api/documents/{document_id}/approval/{action}", response_model=ApprovalStateOut)
def do_action(
    document_id: uuid.UUID,
    action: Action,
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
    data: Annotated[ApprovalIn | None, Body()] = None,
) -> ApprovalStateOut:
    payload = data.model_dump(include=PAYLOAD_FIELDS, exclude_none=True) if data else {}
    approvals.transition(
        db, principal, document_id, action, comments=data.comments if data else None, ctx=ctx, payload=payload
    )
    return ApprovalStateOut(**approvals.state(db, principal, document_id))


@router.get("/api/documents/{document_id}/approval", response_model=ApprovalStateOut)
def get_state(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> ApprovalStateOut:
    return ApprovalStateOut(**approvals.state(db, principal, document_id))


@router.get("/api/documents/{document_id}/approvals", response_model=list[ApprovalEntryOut])
def get_history(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> list[ApprovalEntryOut]:
    return [ApprovalEntryOut(**e.__dict__) for e in approvals.history(db, principal, document_id)]


class BulkIn(BaseModel):
    action: Literal["approve", "approve_publish", "publish", "reject"]
    document_ids: list[uuid.UUID] = Field(min_length=1, description="Tối đa BULK_REVIEW_MAX (20) tài liệu")
    comments: str | None = Field(default=None, max_length=2000, description="Bắt buộc khi reject (lý do chung)")
    confirmed_checks: list[str] = Field(
        default_factory=list,
        description="Duyệt/xuất bản: phải có đủ validity, physical_copy, extraction, metadata",
    )


class BulkItemOut(BaseModel):
    document_id: uuid.UUID
    ok: bool
    approval_status: str | None
    error_code: str | None
    error_message: str | None


class BulkOut(BaseModel):
    batch_id: str
    succeeded: int
    failed: int
    results: list[BulkItemOut]


@router.post("/api/reviews/bulk", response_model=BulkOut)
def bulk_review(data: BulkIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> BulkOut:
    """FR-20: duyệt/xuất bản/từ chối hàng loạt; > 20 → 422 BULK_LIMIT; thiếu checklist → 422 CHECKLIST_REQUIRED."""
    batch_id, results = approvals.bulk(
        db,
        principal,
        action=data.action,
        document_ids=data.document_ids,
        comments=data.comments,
        confirmed_checks=data.confirmed_checks,
        ctx=ctx,
    )
    return BulkOut(
        batch_id=batch_id,
        succeeded=sum(r.ok for r in results),
        failed=sum(not r.ok for r in results),
        results=[BulkItemOut(**r.__dict__) for r in results],
    )


@router.get("/api/reviews", response_model=Page[ReviewItemOut])
def review_queue(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    include_expired: bool = False,
) -> Page[ReviewItemOut]:
    items, total = approvals.review_queue(db, principal, params, include_expired=include_expired)
    return Page(
        items=[ReviewItemOut(**i.__dict__) for i in items], total=total, page=params.page, page_size=params.page_size
    )
