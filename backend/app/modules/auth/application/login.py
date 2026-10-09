"""UC-00 Đăng nhập / đăng xuất (FR-01, SDD mục 14).

- Sai thông tin hoặc tài khoản bị khóa -> 401; sai quá LOGIN_MAX_FAILURES lần trong cửa sổ
  thời gian -> 429. Mọi lần thử được audit.
- Thành công: tạo session MỚI (xoay session) trong store, trả csrf_token.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.users.application import manage as users_manage
from app.modules.users.application import queries as users_q
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import AuthenticationError, TooManyRequestsError
from app.shared.security.passwords import verify_password
from app.shared.security.session import SessionData, get_session_store


@dataclass(frozen=True)
class LoginResult:
    principal: Principal
    session: SessionData


def _rate_key(login: str, ip: str | None) -> str:
    return f"login:{ip or '-'}:{login.strip().lower()}"


def login(db: Session, login_id: str, password: str, ctx: RequestContext, old_session_id: str | None) -> LoginResult:
    store = get_session_store()
    key = _rate_key(login_id, ctx.ip_address)
    creds = users_q.find_credentials(db, login_id)
    ok = verify_password(password, creds.password_hash if creds else None)
    if not ok or creds is None or not creds.is_active:
        failures = store.incr(key, settings.LOGIN_WINDOW_SECONDS)
        record(
            db,
            action="login",
            module="auth",
            actor_id=creds.user_id if creds else None,
            ctx=ctx,
            entity_type="user",
            entity_id=login_id[:50],
            success=False,
            after={"reason": "locked" if (ok and creds and not creds.is_active) else "invalid"},
        )
        db.commit()
        if failures > settings.LOGIN_MAX_FAILURES:
            raise TooManyRequestsError("Đăng nhập sai quá nhiều lần, vui lòng thử lại sau")
        if ok and creds is not None and not creds.is_active:
            raise AuthenticationError("Tài khoản đã bị khóa", code="ACCOUNT_LOCKED")
        raise AuthenticationError("Tên đăng nhập hoặc mật khẩu không đúng", code="INVALID_CREDENTIALS")
    if store.incr(key, settings.LOGIN_WINDOW_SECONDS) > settings.LOGIN_MAX_FAILURES + 1:
        # đã vượt ngưỡng trước đó: vẫn chặn trong cửa sổ, kể cả khi lần này đúng mật khẩu
        raise TooManyRequestsError("Đăng nhập sai quá nhiều lần, vui lòng thử lại sau")
    store.reset(key)
    if old_session_id:
        store.revoke(old_session_id)
    session = store.create(creds.user_id)
    users_manage.mark_login(db, creds.user_id)
    record(
        db, action="login", module="auth", actor_id=creds.user_id, ctx=ctx, entity_type="user", entity_id=creds.user_id
    )
    db.commit()
    principal = users_q.get_principal(db, creds.user_id)
    assert principal is not None  # noqa: S101 - vừa kiểm is_active ở trên
    return LoginResult(principal, session)


def logout(db: Session, principal: Principal, session_id: str, ctx: RequestContext) -> None:
    get_session_store().revoke(session_id)
    record(
        db, action="logout", module="auth", actor_id=principal.id, ctx=ctx, entity_type="user", entity_id=principal.id
    )
    db.commit()
