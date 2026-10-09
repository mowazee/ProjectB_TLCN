"""GET /api/audit (UC-08): chỉ Admin; lọc theo ngày/người/tài liệu/hành động. Không có API sửa/xóa."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.modules.audit.application.queries import AuditFilter, list_logs
from app.modules.auth.presentation.deps import CurrentPrincipal, DbSession, require_roles
from app.modules.users.application.queries import display_names
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID | None
    user_name: str | None
    action: str
    module: str
    entity_type: str | None
    entity_id: str | None
    document_id: uuid.UUID | None
    result: str
    ip_address: str | None
    state_before: dict[str, Any] | None
    state_after: dict[str, Any] | None


@router.get("", response_model=Page[AuditLogOut], dependencies=[Depends(require_roles("ADMIN"))])
def get_audit(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[AuditLogOut]:
    logs, total = list_logs(db, principal, AuditFilter(date_from, date_to, user_id, document_id, action), params)
    names = display_names(db, {x.user_id for x in logs if x.user_id})
    items = [
        AuditLogOut(
            id=x.id,
            created_at=x.created_at,
            user_id=x.user_id,
            user_name=names.get(x.user_id) if x.user_id else None,
            action=x.action,
            module=x.module,
            entity_type=x.entity_type,
            entity_id=x.entity_id,
            document_id=x.document_id,
            result=str(x.result),
            ip_address=x.ip_address,
            state_before=x.state_before,
            state_after=x.state_after,
        )
        for x in logs
    ]
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)
