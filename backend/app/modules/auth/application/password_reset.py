"""v0.17 Quên mật khẩu: gửi link khôi phục qua email (dùng chung cấu hình SMTP_* với chia sẻ ra ngoài FR-18).

- POST forgot: tên đăng nhập/email không tồn tại -> vẫn trả thông báo chung (không dò được tài khoản).
- Tài khoản có thật nhưng không gửi được thư -> 503 EMAIL_SEND_FAILED "Không gửi được email khôi phục mật khẩu, vui
  lòng liên hệ Quản trị viên": tài khoản do Admin khóa (không được khôi phục bằng email), chưa có email hợp lệ, hoặc
  máy chủ thư từ chối/lỗi kết nối. Vì vậy thư được gửi NGAY trong request (không qua hàng đợi) để biết kết quả.
- Giới hạn PASSWORD_RESET_PER_HOUR thư mỗi tài khoản mỗi giờ và SHARE_RATE_PER_MINUTE yêu cầu mỗi IP mỗi phút.
- Link có hiệu lực PASSWORD_RESET_TTL_MINUTES phút, dùng một lần; link mới thay link cũ.
- Đặt lại thành công: thu hồi mọi phiên, mở lại tài khoản bị khóa do nhập sai, ghi audit.
"""

import logging
import re

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.users.application import credentials
from app.shared.config import settings
from app.shared.context import RequestContext
from app.shared.email import email_enabled, get_email_sender
from app.shared.errors import AppError, TooManyRequestsError
from app.shared.security.session import get_session_store

log = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")  # phần domain không chồng lấn: không backtracking
SEND_FAILED_MESSAGE = "Không gửi được email khôi phục mật khẩu, vui lòng liên hệ Quản trị viên"


class EmailNotConfiguredError(AppError):
    status_code = 503
    code = "EMAIL_NOT_CONFIGURED"


class EmailSendFailedError(AppError):
    status_code = 503
    code = "EMAIL_SEND_FAILED"


def enabled() -> bool:
    return email_enabled()


def _limit_ip(ctx: RequestContext) -> None:
    if ctx.ip_address and get_session_store().incr(f"pwreset-ip:{ctx.ip_address}", 60) > settings.SHARE_RATE_PER_MINUTE:
        raise TooManyRequestsError("Quá nhiều yêu cầu, vui lòng thử lại sau")


def _audit_failure(db: Session, ctx: RequestContext, target: credentials.ResetTarget, reason: str) -> None:
    record(
        db,
        action="request_password_reset",
        module="auth",
        actor_id=target.user_id,
        ctx=ctx,
        entity_type="user",
        entity_id=target.user_id,
        success=False,
        after={"reason": reason},
    )
    db.commit()


def _mail_text(full_name: str, url: str) -> str:
    return (
        f"Xin chào {full_name},\n\n"
        "Hệ thống số hóa hồ sơ nhận được yêu cầu khôi phục mật khẩu cho tài khoản của bạn.\n"
        f"Mở link sau để đặt mật khẩu mới (hiệu lực {settings.PASSWORD_RESET_TTL_MINUTES} phút, chỉ dùng được "
        f"một lần):\n{url}\n\n"
        "Nếu tài khoản đang bị khóa do nhập sai mật khẩu, tài khoản sẽ được mở lại sau khi bạn đặt mật khẩu mới.\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này; mật khẩu hiện tại vẫn giữ nguyên."
    )


def request_reset(db: Session, login_id: str, ctx: RequestContext) -> None:
    if not email_enabled():
        raise EmailNotConfiguredError("Hệ thống chưa cấu hình gửi email, vui lòng liên hệ Quản trị viên")
    _limit_ip(ctx)
    target = credentials.find_reset_target(db, login_id)
    if target is None:
        return  # không lộ tài khoản có tồn tại hay không
    if not target.allowed:
        _audit_failure(db, ctx, target, "locked_by_admin")
        raise EmailSendFailedError(SEND_FAILED_MESSAGE)
    if not EMAIL_RE.match(target.email):
        _audit_failure(db, ctx, target, "no_email")
        raise EmailSendFailedError(SEND_FAILED_MESSAGE)
    if get_session_store().incr(f"pwreset-user:{target.user_id}", 3600) > settings.PASSWORD_RESET_PER_HOUR:
        raise TooManyRequestsError("Đã gửi quá nhiều email khôi phục, vui lòng thử lại sau")
    token, row = credentials.create_reset_token(db, target.user_id)
    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/reset-password/{token}"
    try:
        get_email_sender().send(target.email, "Khôi phục mật khẩu", _mail_text(target.full_name, url))
    except Exception as exc:  # SMTP từ chối địa chỉ, sai cấu hình, mất kết nối...
        log.warning("password reset mail failed: %s", type(exc).__name__)
        db.rollback()  # bỏ token vừa tạo
        _audit_failure(db, ctx, target, f"send_failed:{type(exc).__name__}")
        raise EmailSendFailedError(SEND_FAILED_MESSAGE) from exc
    record(
        db,
        action="request_password_reset",
        module="auth",
        actor_id=target.user_id,
        ctx=ctx,
        entity_type="user",
        entity_id=target.user_id,
        after={"expires_at": row.expires_at.isoformat()},
    )
    db.commit()


def check_token(db: Session, token: str) -> str:
    return credentials.check_reset_token(db, token)


def reset_password(db: Session, token: str, new_password: str, ctx: RequestContext) -> bool:
    """Trả True nếu tài khoản vừa được mở khóa."""
    _limit_ip(ctx)
    done = credentials.reset_password(db, token, new_password)
    record(
        db,
        action="reset_password",
        module="auth",
        actor_id=done.user_id,
        ctx=ctx,
        entity_type="user",
        entity_id=done.user_id,
        after={"reactivated": done.reactivated},
    )
    db.commit()
    get_session_store().revoke_user(done.user_id)
    return done.reactivated
