"""UC-32 Chia sẻ tài liệu ra ngoài, UC-33 Xem tài liệu qua link + OTP (FR-18, D-13, SDD v0.13).

- Người tạo: chủ sở hữu, Kiểm duyệt viên phòng ban của tài liệu, Admin; chỉ tài liệu đã xuất bản.
- Link hết hạn tối đa EXTERNAL_SHARE_MAX_HOURS (24 giờ); token ngẫu nhiên 32 byte, chỉ lưu băm SHA-256.
- Người nhận nhập OTP 6 chữ số gửi tới recipient_email (TTL SHARE_OTP_TTL_SECONDS, sai quá SHARE_OTP_MAX_FAILURES
  lần thì khóa SHARE_LOCK_SECONDS); đúng thì cấp phiên xem riêng của link (không phải session người dùng).
- Link mất hiệu lực khi hết hạn, bị thu hồi, tài liệu không còn xuất bản hoặc bị xóa (kiểm ở mỗi request).
- Email gửi bất đồng bộ bằng job EMAIL qua EmailSender; mọi thao tác ghi audit.
"""

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application import queries as documents
from app.modules.jobs.application.create import create_job
from app.modules.jobs.domain.model import JobError
from app.modules.sharing.infrastructure.models import ShareLink
from app.modules.users.application.queries import display_names
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import aware, utcnow
from app.shared.email import email_enabled, get_email_sender
from app.shared.errors import AppError, NotFoundError, UnprocessableError
from app.shared.security.session import get_session_store

EMAIL_KIND = "EMAIL"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class GoneLinkError(AppError):
    status_code = 410
    code = "SHARE_LINK_GONE"


class TooManyAttemptsError(AppError):
    status_code = 429
    code = "TOO_MANY_ATTEMPTS"


class EmailNotConfiguredError(AppError):
    status_code = 503
    code = "EMAIL_NOT_CONFIGURED"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return (name[:2] + "***@" + domain) if domain else "***"


@dataclass
class LinkView:
    id: uuid.UUID
    recipient_email: str
    allow_download: bool
    expires_at: datetime
    revoked_at: datetime | None
    email_status: str
    created_by: str | None
    created_at: datetime
    last_accessed_at: datetime | None
    access_count: int
    status: str  # active | expired | revoked


def _status(link: ShareLink, now: datetime) -> str:
    if link.revoked_at is not None:
        return "revoked"
    if aware(link.expires_at) is not None and aware(link.expires_at) <= now:  # type: ignore[operator]
        return "expired"
    return "active"


def _views(db: Session, links: list[ShareLink]) -> list[LinkView]:
    now = utcnow()
    names = display_names(db, {x.created_by for x in links if x.created_by})
    return [
        LinkView(
            x.id,
            x.recipient_email,
            x.allow_download,
            x.expires_at,
            x.revoked_at,
            x.email_status,
            names.get(x.created_by) if x.created_by else None,
            x.created_at,
            x.last_accessed_at,
            x.access_count,
            _status(x, now),
        )
        for x in links
    ]


def _queue_email(db: Session, document_id: uuid.UUID, to: str, subject: str, text: str, link_id: uuid.UUID) -> None:
    create_job(
        db,
        kind=EMAIL_KIND,
        document_id=document_id,
        queue="default",
        payload={"to": to, "subject": subject, "text": text, "link_id": str(link_id)},
        allow_parallel=True,
    )


def list_links(db: Session, principal: Principal, document_id: uuid.UUID) -> list[LinkView]:
    documents.ensure_can_share(db, principal, document_id)
    links = db.scalars(
        select(ShareLink).where(ShareLink.document_id == document_id).order_by(ShareLink.created_at.desc())
    ).all()
    return _views(db, list(links))


def create_link(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    *,
    recipient_email: str,
    expires_in_hours: int,
    allow_download: bool,
    ctx: RequestContext,
) -> tuple[LinkView, str]:
    """Trả (link, URL đầy đủ - chỉ hiện một lần cho người tạo)."""
    if not email_enabled():
        raise EmailNotConfiguredError("Chưa cấu hình gửi email (SMTP) nên chưa chia sẻ ra ngoài được")
    doc = documents.ensure_can_share(db, principal, document_id)
    email = recipient_email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 255:
        raise UnprocessableError("Email người nhận không hợp lệ", fields={"recipient_email": "invalid"})
    if not 1 <= expires_in_hours <= settings.EXTERNAL_SHARE_MAX_HOURS:
        raise UnprocessableError(
            f"Thời hạn link từ 1 đến {settings.EXTERNAL_SHARE_MAX_HOURS} giờ", fields={"expires_in_hours": "range"}
        )
    token = secrets.token_urlsafe(32)
    link = ShareLink(
        document_id=doc.id,
        token_hash=_hash(token),
        recipient_email=email,
        allow_download=allow_download,
        expires_at=utcnow() + timedelta(hours=expires_in_hours),
        created_by=principal.id,
    )
    db.add(link)
    db.flush()
    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/s/{token}"
    text = (
        f'Bạn được chia sẻ tài liệu "{doc.title}".\n\n'
        f"Mở link sau và nhập mã xác thực được gửi tới email này:\n{url}\n\n"
        f"Link hết hạn lúc {link.expires_at:%H:%M %d/%m/%Y} (UTC). "
        f"{'Được phép tải tài liệu.' if allow_download else 'Chỉ được xem, không tải.'}\n"
        "Nếu bạn không chờ email này, hãy bỏ qua."
    )
    _queue_email(db, doc.id, email, f"Tài liệu được chia sẻ: {doc.title}", text, link.id)
    record(
        db,
        action="create_external_share",
        module="sharing",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="share_link",
        entity_id=link.id,
        document_id=doc.id,
        after={"recipient": email, "expires_at": link.expires_at.isoformat(), "allow_download": allow_download},
    )
    db.commit()
    return _views(db, [link])[0], url


def revoke_link(db: Session, principal: Principal, link_id: uuid.UUID, ctx: RequestContext) -> None:
    link = db.get(ShareLink, link_id)
    if link is None:
        raise NotFoundError("Không tìm thấy link chia sẻ")
    documents.ensure_can_share(db, principal, link.document_id)
    if link.revoked_at is None:
        link.revoked_at = utcnow()
        record(
            db,
            action="revoke_external_share",
            module="sharing",
            actor_id=principal.id,
            ctx=ctx,
            entity_type="share_link",
            entity_id=link.id,
            document_id=link.document_id,
        )
    db.commit()


# ---------------------------------------------------------------- phía người nhận (không đăng nhập)
def _limit_ip(ip: str | None) -> None:
    if ip and get_session_store().incr(f"share-ip:{ip}", 60) > settings.SHARE_RATE_PER_MINUTE:
        raise TooManyAttemptsError("Quá nhiều yêu cầu, vui lòng thử lại sau")


def resolve(db: Session, token: str, ip: str | None = None) -> tuple[ShareLink, Any]:
    """Link + tài liệu nếu link còn hiệu lực; ngược lại 410 (không phân biệt lý do để không lộ thông tin)."""
    _limit_ip(ip)
    link = db.scalar(select(ShareLink).where(ShareLink.token_hash == _hash(token)))
    if link is None:
        raise GoneLinkError("Link không tồn tại hoặc đã hết hiệu lực")
    doc = documents.shareable_document(db, link.document_id)
    if doc is None or _status(link, utcnow()) != "active":
        raise GoneLinkError("Link không tồn tại hoặc đã hết hiệu lực")
    return link, doc


def request_otp(db: Session, token: str, ip: str | None) -> str:
    """Gửi OTP tới email người nhận; trả email đã che một phần để hiển thị."""
    link, doc = resolve(db, token, ip)
    store = get_session_store()
    if store.incr(f"share-otp-sent:{link.id}", settings.SHARE_OTP_TTL_SECONDS) > 5:
        raise TooManyAttemptsError("Đã gửi quá nhiều mã, vui lòng thử lại sau")
    code = f"{secrets.randbelow(10**6):06d}"
    store.put_value(f"share-otp:{link.id}", _hash(code), settings.SHARE_OTP_TTL_SECONDS)
    minutes = settings.SHARE_OTP_TTL_SECONDS // 60
    _queue_email(
        db,
        doc.id,
        link.recipient_email,
        f"Mã xác thực xem tài liệu: {code}",
        f'Mã xác thực để xem tài liệu "{doc.title}" là: {code}\nMã có hiệu lực {minutes} phút. Không chia sẻ mã này.',
        link.id,
    )
    db.commit()
    return _mask(link.recipient_email)


def verify_otp(db: Session, token: str, code: str, ip: str | None, ctx: RequestContext) -> tuple[str, int]:
    """Đúng mã → (id phiên xem, số giây còn hiệu lực)."""
    link, doc = resolve(db, token, ip)
    store = get_session_store()
    fail_key = f"share-otp-fail:{link.id}"
    if store.incr(fail_key, settings.SHARE_LOCK_SECONDS) > settings.SHARE_OTP_MAX_FAILURES:
        raise TooManyAttemptsError("Nhập sai quá nhiều lần, link tạm khóa, vui lòng thử lại sau")
    expected = store.get_value(f"share-otp:{link.id}")
    if not expected or not hmac.compare_digest(expected, _hash(code.strip())):
        raise UnprocessableError(
            "Mã xác thực không đúng hoặc đã hết hạn", code="OTP_INVALID", fields={"code": "invalid"}
        )
    store.reset(fail_key)
    store.delete_value(f"share-otp:{link.id}")
    remaining = int((aware(link.expires_at) - utcnow()).total_seconds())  # type: ignore[operator]
    sid = secrets.token_urlsafe(32)
    store.put_value(f"share-view:{_hash(sid)}", str(link.id), remaining)
    record(
        db,
        action="external_verify",
        module="sharing",
        actor_id=None,
        ctx=ctx,
        entity_type="share_link",
        entity_id=link.id,
        document_id=doc.id,
    )
    db.commit()
    return sid, remaining


def require_view(db: Session, token: str, sid: str | None, ip: str | None) -> tuple[ShareLink, Any]:
    link, doc = resolve(db, token, ip)
    if not sid or get_session_store().get_value(f"share-view:{_hash(sid)}") != str(link.id):
        from app.shared.errors import AuthenticationError

        raise AuthenticationError("Cần nhập mã xác thực", code="OTP_REQUIRED")
    return link, doc


def touch(db: Session, link: ShareLink, action: str, ctx: RequestContext, extra: dict[str, Any] | None = None) -> None:
    link.access_count = (link.access_count or 0) + 1
    link.last_accessed_at = utcnow()
    record(
        db,
        action=action,
        module="sharing",
        actor_id=None,
        ctx=ctx,
        entity_type="share_link",
        entity_id=link.id,
        document_id=link.document_id,
        after={"recipient": link.recipient_email, **(extra or {})},
    )
    db.commit()


def run_email(ctx: Any) -> None:
    """Job EMAIL: gửi thư qua EmailSender; xóa nội dung thư khỏi payload sau khi gửi (thư chứa link/OTP)."""
    p = ctx.payload
    link = db_link = ctx.db.get(ShareLink, uuid.UUID(p["link_id"])) if p.get("link_id") else None
    try:
        get_email_sender().send(p["to"], p["subject"], p["text"])
    except Exception as exc:
        if db_link is not None:
            db_link.email_status = "failed"
        ctx.job.payload = {"to": p.get("to"), "link_id": p.get("link_id"), "error": type(exc).__name__}
        ctx.db.commit()
        raise JobError("EMAIL_FAILED", f"Không gửi được email: {type(exc).__name__}") from exc
    if link is not None:
        link.email_status = "sent"
    ctx.job.payload = {"to": p.get("to"), "link_id": p.get("link_id"), "sent": True}
    ctx.db.commit()
