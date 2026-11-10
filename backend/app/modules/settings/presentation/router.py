"""API cấu hình hệ thống (SDD v0.13 mục 7.1, FR-14):
GET/PUT /api/admin/settings   chỉ Admin; trash_retention_days 1-365, audit_retention_days 180-3650 (ngoài khoảng 422)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_roles
from app.modules.settings.application import retention

router = APIRouter(prefix="/api/admin/settings", tags=["settings"], dependencies=[Depends(require_roles("ADMIN"))])


class SettingsOut(BaseModel):
    trash_retention_days: int = Field(description="Số ngày giữ tài liệu trong thùng rác trước khi xóa cứng")
    audit_retention_days: int = Field(description="Số ngày lưu audit log (tối thiểu 180)")


class SettingsIn(BaseModel):
    trash_retention_days: int | None = None
    audit_retention_days: int | None = None


@router.get("", response_model=SettingsOut)
def get_settings(db: DbSession, principal: CurrentPrincipal) -> SettingsOut:
    return SettingsOut(**retention.get_retention(db))


@router.put("", response_model=SettingsOut)
def put_settings(data: SettingsIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> SettingsOut:
    return SettingsOut(**retention.update_retention(db, principal, data.model_dump(exclude_none=True), ctx))
