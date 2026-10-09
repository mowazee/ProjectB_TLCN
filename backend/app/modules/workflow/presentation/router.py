"""API workflow (SDD 7.2, P2-01):
POST /api/documents/{id}/approval/{action}   action ∈ submit, approve, reject, publish, unpublish; sai trạng thái 409
GET  /api/documents/{id}/approval            trạng thái hiện tại + action được phép (cho React hiện nút)
GET  /api/documents/{id}/approvals           lịch sử duyệt
GET  /api/reviews                            hàng chờ duyệt (Kiểm duyệt/Admin)
"""

import uuid
from datetime import datetime
from typing import Annotated

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


@router.post("/api/documents/{document_id}/approval/{action}", response_model=ApprovalStateOut)
def do_action(
    document_id: uuid.UUID,
    action: Action,
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
    data: Annotated[ApprovalIn | None, Body()] = None,
) -> ApprovalStateOut:
    approvals.transition(db, principal, document_id, action, comments=data.comments if data else None, ctx=ctx)
    return ApprovalStateOut(**approvals.state(db, principal, document_id))


@router.get("/api/documents/{document_id}/approval", response_model=ApprovalStateOut)
def get_state(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> ApprovalStateOut:
    return ApprovalStateOut(**approvals.state(db, principal, document_id))


@router.get("/api/documents/{document_id}/approvals", response_model=list[ApprovalEntryOut])
def get_history(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> list[ApprovalEntryOut]:
    return [ApprovalEntryOut(**e.__dict__) for e in approvals.history(db, principal, document_id)]


@router.get("/api/reviews", response_model=Page[ReviewItemOut])
def review_queue(
    db: DbSession, principal: CurrentPrincipal, params: Annotated[PageParams, Depends(page_params)]
) -> Page[ReviewItemOut]:
    items, total = approvals.review_queue(db, principal, params)
    return Page(
        items=[ReviewItemOut(**i.__dict__) for i in items], total=total, page=params.page, page_size=params.page_size
    )
