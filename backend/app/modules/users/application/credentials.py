"""v0.17: khóa tài khoản khi nhập sai mật khẩu liên tiếp và khôi phục mật khẩu bằng link email (dữ liệu của users).

- Sai ACCOUNT_LOCK_THRESHOLD lần liên tiếp -> is_active = False, locked_reason = "failed_logins"; đăng nhập đúng thì
  bộ đếm về 0.
- Admin khóa -> locked_reason = "admin"; Admin mở khóa -> xóa lý do và bộ đếm (manage.update_user).
- Link khôi phục: token ngẫu nhiên 32 byte, chỉ lưu băm SHA-256, hết hạn sau PASSWORD_RESET_TTL_MINUTES, dùng một lần.
  Đặt lại mật khẩu thành công thì mở lại tài khoản bị khóa do nhập sai; tài khoản do Admin khóa không được khôi phục
  bằng email (không gửi link).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.modules.users.application.account import MIN_PASSWORD, _field
from app.modules.users.infrastructure.models import PasswordResetToken, User
from app.shared.config import settings
from app.shared.db import aware, utcnow
from app.shared.errors import GoneError, UnprocessableError
from app.shared.security.passwords import hash_password

LOCK_FAILED_LOGINS = "failed_logins"
LOCK_ADMIN = "admin"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class FailedLogin:
    failures: int
    locked: bool  # vừa bị khóa ở lần sai này


def register_failed_login(db: Session, user_id: uuid.UUID) -> FailedLogin:
    """Tăng bộ đếm bằng một câu UPDATE (an toàn khi nhiều request song song); đủ ngưỡng thì khóa. Chưa commit."""
    db.execute(update(User).where(User.id == user_id).values(failed_login_count=User.failed_login_count + 1))
    user = db.get(User, user_id)
    if user is None:
        return FailedLogin(0, False)
    db.refresh(user, ["failed_login_count", "is_active"])
    locked = False
    if user.is_active and user.failed_login_count >= settings.ACCOUNT_LOCK_THRESHOLD:
        user.is_active = False
        user.locked_reason = LOCK_FAILED_LOGINS
        locked = True
    return FailedLogin(user.failed_login_count, locked)


def clear_failed_logins(db: Session, user_id: uuid.UUID) -> None:
    db.execute(update(User).where(User.id == user_id, User.failed_login_count != 0).values(failed_login_count=0))


@dataclass(frozen=True)
class ResetTarget:
    user_id: uuid.UUID
    email: str
    full_name: str
    allowed: bool  # False: tài khoản do Admin khóa - không được khôi phục bằng email


def find_reset_target(db: Session, login: str) -> ResetTarget | None:
    """Tài khoản theo tên đăng nhập/email; chỉ được nhận link khi đang hoạt động hoặc bị khóa do nhập sai mật khẩu."""
    key = login.strip().lower()
    user = db.scalar(select(User).where(or_(User.username == key, User.email == key)))
    if user is None:
        return None
    allowed = user.is_active or user.locked_reason == LOCK_FAILED_LOGINS
    return ResetTarget(user.id, (user.email or "").strip(), user.full_name, allowed)


def create_reset_token(db: Session, user_id: uuid.UUID) -> tuple[str, PasswordResetToken]:
    """Tạo token mới, hủy các link cũ chưa dùng của tài khoản (chỉ link mới nhất còn hiệu lực). Chưa commit."""
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    token = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user_id,
        token_hash=_hash(token),
        expires_at=utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
    )
    db.add(row)
    db.flush()
    return token, row


def _valid_token(db: Session, token: str) -> tuple[PasswordResetToken, User]:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(token)))
    user = db.get(User, row.user_id) if row is not None else None
    expires = aware(row.expires_at) if row is not None else None
    if (
        row is None
        or user is None
        or row.used_at is not None
        or expires is None
        or expires <= utcnow()
        or not (user.is_active or user.locked_reason == LOCK_FAILED_LOGINS)
    ):
        raise GoneError("Link khôi phục mật khẩu không hợp lệ hoặc đã hết hạn", code="RESET_LINK_INVALID")
    return row, user


def check_reset_token(db: Session, token: str) -> str:
    """Trả tên đăng nhập của tài khoản nếu link còn hiệu lực (trang đặt lại mật khẩu hiển thị); 410 nếu không."""
    return _valid_token(db, token)[1].username


@dataclass(frozen=True)
class ResetDone:
    user_id: uuid.UUID
    reactivated: bool


def reset_password(db: Session, token: str, new_password: str) -> ResetDone:
    """Đổi mật khẩu bằng link; mở lại tài khoản bị khóa do nhập sai; hủy mọi link của tài khoản. Chưa commit."""
    row, user = _valid_token(db, token)
    if len(new_password) < MIN_PASSWORD:
        raise UnprocessableError(
            f"Mật khẩu mới phải có ít nhất {MIN_PASSWORD} ký tự", fields=_field("new_password", "too_short")
        )
    reactivated = not user.is_active
    user.password_hash = hash_password(new_password)
    user.is_active = True
    user.locked_reason = None
    user.failed_login_count = 0
    row.used_at = utcnow()
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.id != row.id))
    return ResetDone(user.id, reactivated)
