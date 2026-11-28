"""UC-00 Đăng nhập / đăng xuất (FR-01, SDD mục 14; v0.17 khóa tài khoản).

- Sai tên đăng nhập hoặc mật khẩu: 401 INVALID_CREDENTIALS với cùng một thông báo (kèm lưu ý khóa sau
  ACCOUNT_LOCK_THRESHOLD lần, không nêu số lần còn lại để không lộ tài khoản có tồn tại). Sai mật khẩu liên tiếp
  ACCOUNT_LOCK_THRESHOLD lần thì khóa -> 401 ACCOUNT_LOCKED "liên hệ Quản trị viên". Đăng nhập đúng thì bộ đếm về 0.
  Tài khoản bị khóa do nhập sai mở lại bằng Admin hoặc chức năng quên mật khẩu.
- Tên đăng nhập không tồn tại: quá LOGIN_MAX_FAILURES lần trong cửa sổ (theo IP + tên) -> 429.
- Mọi lần thử được audit. Thành công: tạo session MỚI (xoay session) trong store, trả csrf_token.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.users.application import credentials
from app.modules.users.application import manage as users_manage
from app.modules.users.application import queries as users_q
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import AuthenticationError, TooManyRequestsError
from app.shared.security.passwords import verify_password
from app.shared.security.session import SessionData, get_session_store

LOCKED_MESSAGE = "Tài khoản đã bị khóa, vui lòng liên hệ Quản trị viên"


def _invalid_error() -> AuthenticationError:
    return AuthenticationError(
        "Tên đăng nhập hoặc mật khẩu không đúng, lưu ý tài khoản sẽ bị khóa nếu nhập sai mật khẩu quá "
        f"{settings.ACCOUNT_LOCK_THRESHOLD} lần",
        code="INVALID_CREDENTIALS",
    )


@dataclass(frozen=True)
class LoginResult:
    principal: Principal
    session: SessionData


def _rate_key(login: str, ip: str | None) -> str:
    return f"login:{ip or '-'}:{login.strip().lower()}"


def _fail(
    db: Session, ctx: RequestContext, login_id: str, actor_id: uuid.UUID | None, reason: str, **extra: object
) -> None:
    record(
        db,
        action="login",
        module="auth",
        actor_id=actor_id,
        ctx=ctx,
        entity_type="user",
        entity_id=login_id[:50],
        success=False,
        after={"reason": reason, **extra},
    )
    db.commit()


def _locked_error() -> AuthenticationError:
    return AuthenticationError(LOCKED_MESSAGE, code="ACCOUNT_LOCKED")


def login(db: Session, login_id: str, password: str, ctx: RequestContext, old_session_id: str | None) -> LoginResult:
    store = get_session_store()
    creds = users_q.find_credentials(db, login_id)
    ok = verify_password(password, creds.password_hash if creds else None)
    if creds is None:
        # chống dò hàng loạt tên đăng nhập: giới hạn theo IP + tên trong cửa sổ thời gian
        failures = store.incr(_rate_key(login_id, ctx.ip_address), settings.LOGIN_WINDOW_SECONDS)
        _fail(db, ctx, login_id, None, "invalid")
        if failures > settings.LOGIN_MAX_FAILURES:
            raise TooManyRequestsError("Đăng nhập sai quá nhiều lần, vui lòng thử lại sau")
        raise _invalid_error()
    if not creds.is_active:
        _fail(db, ctx, login_id, creds.user_id, "locked")
        # Tài khoản do Admin khóa chỉ báo "bị khóa" khi đúng mật khẩu (không lộ trạng thái cho người đoán mò);
        # khóa do nhập sai thì luôn báo để người dùng biết liên hệ Admin hoặc dùng quên mật khẩu.
        if ok or creds.locked_reason == credentials.LOCK_FAILED_LOGINS:
            raise _locked_error()
        raise _invalid_error()
    if not ok:
        result = credentials.register_failed_login(db, creds.user_id)
        _fail(db, ctx, login_id, creds.user_id, "invalid", failures=result.failures)
        if result.locked:
            store.revoke_user(creds.user_id)
            record(
                db,
                action="auto_lock_user",
                module="auth",
                actor_id=None,
                ctx=ctx,
                entity_type="user",
                entity_id=creds.user_id,
                after={"reason": credentials.LOCK_FAILED_LOGINS, "failures": result.failures},
            )
            db.commit()
            raise _locked_error()
        raise _invalid_error()
    credentials.clear_failed_logins(db, creds.user_id)
    if old_session_id:
        store.revoke(old_session_id)
    session = store.create(creds.user_id)
    users_manage.mark_login(db, creds.user_id)
    record(
        db, action="login", module="auth", actor_id=creds.user_id, ctx=ctx, entity_type="user", entity_id=creds.user_id
    )
    db.commit()
    principal = users_q.get_principal(db, creds.user_id)
    # Tài khoản vừa bị khóa/xóa giữa chừng: không để lại session. Không dùng assert (bị bỏ khi chạy python -O).
    if principal is None:
        store.revoke(session.session_id)
        raise _invalid_error()
    return LoginResult(principal, session)


def logout(db: Session, principal: Principal, session_id: str, ctx: RequestContext) -> None:
    get_session_store().revoke(session_id)
    record(
        db, action="logout", module="auth", actor_id=principal.id, ctx=ctx, entity_type="user", entity_id=principal.id
    )
    db.commit()
