"""FR-09 (UC-25): tài khoản của chính người dùng - xem, sửa họ tên/số điện thoại, đổi mật khẩu.

Người dùng không tự đổi tên đăng nhập, email, vai trò, phòng ban (chỉ Admin qua UC-06).
Đổi mật khẩu: kiểm mật khẩu hiện tại (sai quá LOGIN_MAX_FAILURES lần trong cửa sổ -> 429 như đăng nhập),
thu hồi MỌI phiên của người dùng rồi tạo phiên mới cho chính trình duyệt đang dùng.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.users.infrastructure.models import User
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import InvalidInputError, NotFoundError, TooManyRequestsError, UnprocessableError
from app.shared.security.passwords import hash_password, verify_password
from app.shared.security.session import SessionData, get_session_store

MIN_PASSWORD = 8


def _field(name: str, code: str) -> dict[str, str]:
    """fields của lỗi 4xx; tách hàm để bandit B105 không nhầm {"..._password": "wrong"} là mật khẩu viết cứng."""
    return {name: code}


@dataclass(frozen=True)
class AccountView:
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    phone: str | None
    department_id: int | None
    department_name: str | None
    roles: list[str]
    last_login_at: object
    created_at: object


def _me(db: Session, principal: Principal) -> User:
    user = db.get(User, principal.id)
    if user is None or not user.is_active:
        raise NotFoundError("Không tìm thấy tài khoản")
    return user


def _view(u: User) -> AccountView:
    return AccountView(
        u.id,
        u.username,
        u.email,
        u.full_name,
        u.phone,
        u.department_id,
        u.department.name if u.department else None,
        sorted(u.role_codes),
        u.last_login_at,
        u.created_at,
    )


def get_account(db: Session, principal: Principal) -> AccountView:
    return _view(_me(db, principal))


def update_profile(
    db: Session, principal: Principal, changes: dict[str, str | None], ctx: RequestContext
) -> AccountView:
    user = _me(db, principal)
    before = {"full_name": user.full_name, "phone": user.phone}
    if "full_name" in changes:
        name = (changes["full_name"] or "").strip()
        if not name:
            raise UnprocessableError("Họ tên không được để trống", fields={"full_name": "required"})
        user.full_name = name
    if "phone" in changes:
        user.phone = (changes["phone"] or "").strip() or None
    after = {"full_name": user.full_name, "phone": user.phone}
    if after != before:
        record(
            db,
            action="update_account",
            module="users",
            actor_id=user.id,
            ctx=ctx,
            entity_type="user",
            entity_id=user.id,
            before=before,
            after=after,
        )
    db.commit()
    return _view(user)


def change_password(db: Session, principal: Principal, current: str, new: str, ctx: RequestContext) -> SessionData:
    """Trả phiên MỚI cho trình duyệt hiện tại; mọi phiên cũ (kể cả phiên đang dùng) bị thu hồi."""
    user = _me(db, principal)
    store = get_session_store()
    key = f"pwchange:{user.id}"
    if not verify_password(current, user.password_hash):
        failures = store.incr(key, settings.LOGIN_WINDOW_SECONDS)
        record(
            db,
            action="change_password",
            module="users",
            actor_id=user.id,
            ctx=ctx,
            entity_type="user",
            entity_id=user.id,
            success=False,
            after={"reason": "wrong_password"},
        )
        db.commit()
        if failures > settings.LOGIN_MAX_FAILURES:
            raise TooManyRequestsError("Nhập sai mật khẩu quá nhiều lần, vui lòng thử lại sau")
        raise InvalidInputError(
            "Mật khẩu hiện tại không đúng", code="WRONG_PASSWORD", fields=_field("current_password", "wrong")
        )
    if store.incr(key, settings.LOGIN_WINDOW_SECONDS) > settings.LOGIN_MAX_FAILURES + 1:
        # như đăng nhập: đã vượt ngưỡng thì chặn hết cửa sổ, kể cả khi lần này đúng (chống dò bằng phiên bị lộ)
        raise TooManyRequestsError("Nhập sai mật khẩu quá nhiều lần, vui lòng thử lại sau")
    if len(new) < MIN_PASSWORD:
        raise UnprocessableError(
            f"Mật khẩu mới phải có ít nhất {MIN_PASSWORD} ký tự", fields=_field("new_password", "too_short")
        )
    if verify_password(new, user.password_hash):
        raise UnprocessableError("Mật khẩu mới phải khác mật khẩu hiện tại", fields=_field("new_password", "unchanged"))
    store.reset(key)
    user.password_hash = hash_password(new)
    revoked = store.revoke_user(user.id)
    record(
        db,
        action="change_password",
        module="users",
        actor_id=user.id,
        ctx=ctx,
        entity_type="user",
        entity_id=user.id,
        after={"revoked_sessions": revoked},
    )
    db.commit()
    return store.create(user.id)
