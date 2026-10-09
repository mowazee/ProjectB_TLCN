"""API rollback (SDD 7.2, P2-09), chỉ Admin:
GET  /api/audit/{id}/rollback   xem trước: có hỗ trợ không, dữ liệu đã đổi sau đó chưa
POST /api/audit/{id}/rollback   thực hiện; 409 ROLLBACK_STALE nếu đã đổi tiếp (trừ khi confirm=true)
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.rollback.application import rollback

router = APIRouter(prefix="/api/audit", tags=["rollback"], dependencies=[Depends(require_feature("rollback"))])


class RollbackIn(BaseModel):
    confirm: bool = False


class RollbackOut(BaseModel):
    log_id: int
    kind: str
    supported: bool
    changed_since: bool
    current: dict[str, Any]
    target: dict[str, Any]


@router.get("/{log_id}/rollback", response_model=RollbackOut)
def preview(log_id: int, db: DbSession, principal: CurrentPrincipal) -> RollbackOut:
    return RollbackOut(**rollback.plan(db, principal, log_id).__dict__)


@router.post("/{log_id}/rollback", response_model=RollbackOut)
def do_rollback(
    log_id: int,
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
    data: Annotated[RollbackIn | None, Body()] = None,
) -> RollbackOut:
    p = rollback.execute(db, principal, log_id, confirm=bool(data and data.confirm), ctx=ctx)
    return RollbackOut(**p.__dict__)
