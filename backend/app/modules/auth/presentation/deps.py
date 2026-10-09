"""Dependency dùng chung cho router của mọi module (Đặc tả đề tài v0.5 mục 6):
current_principal, require_roles, require_feature, request context.

current_principal kiểm session (Redis), user còn active, và với request ghi (POST/PUT/
PATCH/DELETE) kiểm X-CSRF-Token gắn với session + Origin (SDD mục 14).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.modules.users.application.queries import get_principal
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import get_db
from app.shared.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.shared.logging import request_id_var
from app.shared.security.csrf import CSRF_HEADER, UNSAFE_METHODS, origin_allowed, tokens_match
from app.shared.security.session import SessionData, get_session_store

DbSession = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class AuthState:
    principal: Principal
    session: SessionData


def request_context(request: Request) -> RequestContext:
    return RequestContext(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=request_id_var.get(),
    )


def check_origin(request: Request) -> None:
    if not origin_allowed(request.headers.get("origin"), request.headers.get("referer"), request.headers.get("host")):
        raise PermissionDeniedError("Origin không hợp lệ", code="ORIGIN_REJECTED")


def auth_state(request: Request, db: DbSession) -> AuthState:
    sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not sid:
        raise AuthenticationError("Vui lòng đăng nhập")
    store = get_session_store()
    session = store.get(sid)
    if session is None:
        raise AuthenticationError("Phiên đăng nhập đã hết hạn")
    principal = get_principal(db, session.user_id)
    if principal is None:  # bị khóa/xóa: thu hồi phiên
        store.revoke(sid)
        raise AuthenticationError("Tài khoản không còn hiệu lực")
    if request.method in UNSAFE_METHODS:
        check_origin(request)
        if not tokens_match(session.csrf_token, request.headers.get(CSRF_HEADER)):
            raise PermissionDeniedError("CSRF token không hợp lệ", code="CSRF_FAILED")
    store.touch(sid)
    return AuthState(principal, session)


def current_principal(state: Annotated[AuthState, Depends(auth_state)]) -> Principal:
    return state.principal


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
Ctx = Annotated[RequestContext, Depends(request_context)]


def require_roles(*roles: str) -> Callable[[Principal], Principal]:
    def _dep(principal: CurrentPrincipal) -> Principal:
        if not principal.has_any(*roles):
            raise PermissionDeniedError("Bạn không có quyền thực hiện thao tác này")
        return principal

    return _dep


def require_feature(feature: str) -> Callable[[], None]:
    """Router P2 chỉ được gắn khi cờ bật; dependency này là lớp chặn thứ hai (trả 404)."""

    def _dep() -> None:
        if feature not in settings.features_enabled:
            raise NotFoundError("Tính năng chưa được bật")

    return _dep


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise NotFoundError("Không tìm thấy") from exc
