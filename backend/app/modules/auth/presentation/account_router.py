"""API tài khoản của chính người dùng (SDD v0.7 mục 7.1, FR-09, UC-25):
GET   /api/account            thông tin tài khoản
PATCH /api/account            sửa họ tên, số điện thoại
POST  /api/account/password   đổi mật khẩu -> 204; cookie phiên mới, các phiên khác bị thu hồi
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession
from app.modules.auth.presentation.router import _set_cookie
from app.modules.users.application import account

router = APIRouter(prefix="/api/account", tags=["account"])


class AccountOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    phone: str | None
    department_id: int | None
    department_name: str | None
    roles: list[str]
    last_login_at: datetime | None
    created_at: datetime


class AccountPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


def _out(v: account.AccountView) -> AccountOut:
    return AccountOut.model_validate(v, from_attributes=True)


@router.get("", response_model=AccountOut)
def get_account(db: DbSession, principal: CurrentPrincipal) -> AccountOut:
    return _out(account.get_account(db, principal))


@router.patch("", response_model=AccountOut)
def update_account(data: AccountPatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> AccountOut:
    return _out(account.update_profile(db, principal, data.model_dump(exclude_unset=True), ctx))


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> Response:
    session = account.change_password(db, principal, data.current_password, data.new_password, ctx)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_cookie(resp, session.session_id)  # phiên mới; React gọi lại /api/auth/me để lấy csrf_token mới
    return resp
