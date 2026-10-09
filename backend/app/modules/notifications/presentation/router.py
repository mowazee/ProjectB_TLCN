"""API notifications (SDD 7.2, P2-07):
GET  /api/notifications              thông báo của người dùng hiện tại, phân trang (+ unread)
POST /api/notifications/{id}/read    đánh dấu đã đọc
POST /api/notifications/read-all     đánh dấu tất cả đã đọc (tiện ích cho chuông thông báo)
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.presentation.deps import CurrentPrincipal, DbSession, require_feature
from app.modules.notifications.application import service
from app.shared.http import page_params
from app.shared.pagination import PageParams

router = APIRouter(
    prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(require_feature("notifications"))]
)


class NotificationOut(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    is_read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    page: int
    page_size: int
    unread: int


def _out(n: object) -> NotificationOut:
    return NotificationOut.model_validate(n, from_attributes=True)


@router.get("", response_model=NotificationPage)
def list_notifications(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    unread_only: bool = False,
) -> NotificationPage:
    items, total, unread = service.list_for_user(db, principal, params, unread_only=unread_only)
    return NotificationPage(
        items=[_out(n) for n in items], total=total, page=params.page, page_size=params.page_size, unread=unread
    )


@router.post("/read-all")
def read_all(db: DbSession, principal: CurrentPrincipal) -> dict[str, int]:
    return {"updated": service.mark_all_read(db, principal)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def read_one(notification_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> NotificationOut:
    return _out(service.mark_read(db, principal, notification_id))
