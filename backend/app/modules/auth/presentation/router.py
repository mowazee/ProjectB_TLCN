"""API auth (SDD mục 7.1): POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout.

v0.17: GET /api/auth/options, POST /api/auth/forgot-password, GET/POST /api/auth/reset-password/{token}
(công khai, không cần đăng nhập; kiểm Origin như đăng nhập).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.modules.auth.application import login as login_uc
from app.modules.auth.application import password_reset as reset_uc
from app.modules.auth.presentation.deps import AuthState, Ctx, DbSession, auth_state, check_origin
from app.shared.config import settings
from app.shared.context import Principal

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100, description="Username hoặc email")
    password: str = Field(min_length=1, max_length=128)


class UserBrief(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    department_id: int | None


class SessionOut(BaseModel):
    user: UserBrief
    roles: list[str]
    csrf_token: str
    features: list[str]


def _out(principal: Principal, csrf: str) -> SessionOut:
    return SessionOut(
        user=UserBrief(
            id=principal.id,
            username=principal.username,
            full_name=principal.full_name,
            department_id=principal.department_id,
        ),
        roles=sorted(principal.roles),
        csrf_token=csrf,
        features=sorted(settings.enabled_features),
    )


def _set_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        session_id,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
    )


@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, request: Request, response: Response, db: DbSession, ctx: Ctx) -> SessionOut:
    check_origin(request)
    result = login_uc.login(db, data.username, data.password, ctx, request.cookies.get(settings.SESSION_COOKIE_NAME))
    _set_cookie(response, result.session.session_id)
    return _out(result.principal, result.session.csrf_token)


@router.get("/me", response_model=SessionOut)
def me(state: Annotated[AuthState, Depends(auth_state)]) -> SessionOut:
    return _out(state.principal, state.session.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(state: Annotated[AuthState, Depends(auth_state)], db: DbSession, ctx: Ctx) -> Response:
    login_uc.logout(db, state.principal, state.session.session_id, ctx)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(settings.SESSION_COOKIE_NAME, path="/api")
    return resp


class AuthOptionsOut(BaseModel):
    password_reset: bool = Field(description="Đã cấu hình SMTP: hiện chức năng Quên mật khẩu")
    password_reset_ttl_minutes: int


class ForgotIn(BaseModel):
    login: str = Field(min_length=1, max_length=100, description="Tên đăng nhập hoặc email")


class MessageOut(BaseModel):
    message: str


class ResetCheckOut(BaseModel):
    username: str


class ResetIn(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)


class ResetOut(BaseModel):
    message: str
    reactivated: bool = Field(description="Tài khoản bị khóa do nhập sai mật khẩu vừa được mở lại")


@router.get("/options", response_model=AuthOptionsOut)
def options() -> AuthOptionsOut:
    """Tùy chọn của trang đăng nhập (không cần đăng nhập)."""
    return AuthOptionsOut(
        password_reset=reset_uc.enabled(), password_reset_ttl_minutes=settings.PASSWORD_RESET_TTL_MINUTES
    )


@router.post("/forgot-password", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(data: ForgotIn, request: Request, db: DbSession, ctx: Ctx) -> MessageOut:
    """Gửi link khôi phục tới email của tài khoản. Tài khoản không tồn tại vẫn nhận thông báo chung; tài khoản do
    Admin khóa, chưa có email hợp lệ hoặc máy chủ thư lỗi -> 503 EMAIL_SEND_FAILED."""
    check_origin(request)
    reset_uc.request_reset(db, data.login, ctx)
    return MessageOut(
        message="Nếu thông tin khớp với một tài khoản, email hướng dẫn khôi phục mật khẩu đã được gửi. "
        f"Link có hiệu lực {settings.PASSWORD_RESET_TTL_MINUTES} phút."
    )


@router.get("/reset-password/{token}", response_model=ResetCheckOut)
def check_reset_link(token: str, db: DbSession) -> ResetCheckOut:
    """Kiểm link khôi phục còn hiệu lực; 410 RESET_LINK_INVALID nếu sai, đã dùng hoặc hết hạn."""
    return ResetCheckOut(username=reset_uc.check_token(db, token))


@router.post("/reset-password/{token}", response_model=ResetOut)
def reset_password(token: str, data: ResetIn, request: Request, db: DbSession, ctx: Ctx) -> ResetOut:
    """Đặt mật khẩu mới bằng link; thu hồi mọi phiên; mở lại tài khoản bị khóa do nhập sai mật khẩu."""
    check_origin(request)
    reactivated = reset_uc.reset_password(db, token, data.new_password, ctx)
    return ResetOut(
        message="Đã đặt mật khẩu mới" + (", tài khoản đã được mở khóa" if reactivated else ""),
        reactivated=reactivated,
    )
