"""Hiệu lực tài liệu (FR-19, D-14 - SDD v0.14).

- change(): PUT /api/documents/{id}/validity - chủ sở hữu khi Nháp/Bị từ chối (hoặc cờ workflow tắt); Kiểm duyệt
  viên phòng ban của tài liệu và Admin mọi trạng thái; đã duyệt/đã xuất bản bắt buộc lý do.
- declare_on_submit(): hook "trước khi gửi duyệt" - bắt buộc chọn hiệu lực (cùng hộp thoại bản cứng D-12).
- apply_review(): Kiểm duyệt viên xác nhận/sửa hiệu lực khi duyệt (workflow gọi).
- run_scheduled(): Celery beat - chuyển effective_until quá hạn sang expired, nhắc chủ sở hữu trước hạn.
Mọi thay đổi ghi audit (change_validity, validity_expired) - lịch sử tài liệu giữ vĩnh viễn (D-15).
"""

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application.queries import ensure_can_view, scope_of
from app.modules.documents.domain import policies
from app.modules.documents.domain.lifecycle import LifecycleStatus
from app.modules.documents.domain.validity import (
    REASON_MAX,
    REASON_MIN,
    ValidityStatus,
    check_input,
    days_left,
    label,
)
from app.modules.documents.infrastructure.models import Document
from app.modules.users.application.queries import active_emails
from app.shared.config import settings
from app.shared.context import SYSTEM_CONTEXT, Principal, RequestContext
from app.shared.db import SessionLocal, utcnow
from app.shared.email import email_enabled, get_email_sender
from app.shared.errors import PermissionDeniedError, UnprocessableError
from app.shared.notify import get_notifier

log = logging.getLogger(__name__)


def today() -> date:
    """Ngày hiện tại theo giờ hệ thống (APP_TIMEZONE) - mốc 23:59 của D-14."""
    return datetime.now(settings.tz).date()


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise UnprocessableError(
        "Ngày hết hiệu lực không đúng định dạng", code="INVALID_VALID_UNTIL", fields={"valid_until": "invalid"}
    )


def validate(status: Any, valid_until: Any) -> tuple[ValidityStatus, date | None]:
    """Kiểm dữ liệu nhập; trả (trạng thái, ngày) đã chuẩn hóa. Ngày chỉ giữ cho effective_until."""
    if status in (None, ""):
        raise UnprocessableError(
            "Hãy chọn hiệu lực của tài liệu", code="VALIDITY_REQUIRED", fields={"validity_status": "required"}
        )
    until = _parse_date(valid_until)
    err = check_input(str(status), until, today())
    if err:
        code, message = err
        field = "valid_until" if code == "INVALID_VALID_UNTIL" else "validity_status"
        raise UnprocessableError(message, code=code, fields={field: "invalid"})
    st = ValidityStatus(str(status))
    return st, until if st == ValidityStatus.EFFECTIVE_UNTIL else None


def _snap(doc: Document) -> dict[str, Any]:
    return {
        "validity_status": str(doc.validity_status),
        "valid_until": doc.valid_until.isoformat() if doc.valid_until else None,
    }


def _apply(
    db: Session,
    doc: Document,
    status: ValidityStatus,
    until: date | None,
    *,
    actor_id: uuid.UUID | None,
    ctx: RequestContext,
    reason: str | None,
    action: str = "change_validity",
) -> bool:
    if str(doc.validity_status) == status.value and doc.valid_until == until:
        return False
    before = _snap(doc)
    if doc.valid_until != until:
        doc.validity_reminded_on = None  # đổi ngày hết hạn thì nhắc lại theo ngày mới
    doc.validity_status = status
    doc.valid_until = until
    doc.validity_updated_by = actor_id
    doc.validity_updated_at = utcnow()
    record(
        db,
        action=action,
        module="documents",
        actor_id=actor_id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        before=before,
        after={**_snap(doc), "reason": reason},
    )
    return True


def change(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    *,
    validity_status: Any,
    valid_until: Any = None,
    reason: str | None = None,
    ctx: RequestContext,
) -> Document:
    doc = ensure_can_view(db, principal, document_id)
    scope = scope_of(doc)
    if not policies.can_change_validity(principal, scope):
        raise PermissionDeniedError(
            "Chỉ chủ sở hữu (khi Nháp / Bị từ chối), Kiểm duyệt viên phòng ban của tài liệu hoặc Quản trị viên "
            "được đổi hiệu lực"
        )
    status, until = validate(validity_status, valid_until)
    reason = (reason or "").strip() or None
    if policies.validity_reason_required(scope) and (reason is None or len(reason) < REASON_MIN):
        raise UnprocessableError(
            f"Tài liệu đã duyệt/xuất bản: hãy nhập lý do đổi hiệu lực (tối thiểu {REASON_MIN} ký tự)",
            code="REASON_REQUIRED",
            fields={"reason": "required"},
        )
    if reason and len(reason) > REASON_MAX:
        raise UnprocessableError(f"Lý do tối đa {REASON_MAX} ký tự", fields={"reason": "too_long"})
    _apply(db, doc, status, until, actor_id=principal.id, ctx=ctx, reason=reason)
    db.commit()
    return doc


def declare_on_submit(
    db: Session, principal: Principal, document_id: uuid.UUID, payload: dict[str, Any], ctx: RequestContext
) -> None:
    """Hook trước khi gửi duyệt (FR-19): bắt buộc chọn hiệu lực; không commit (workflow commit).

    Gửi lại (sau khi bị từ chối/trả lại) mà không gửi kèm hiệu lực thì giữ hiệu lực đã khai báo trước đó; tài liệu
    chưa từng khai báo (validity_updated_at NULL, kể cả dữ liệu trước v0.14) phải chọn.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        return
    if payload.get("validity_status") in (None, "") and doc.validity_updated_at is not None:
        if doc.validity_status == ValidityStatus.EFFECTIVE_UNTIL:
            validate(str(doc.validity_status), doc.valid_until)  # ngày đã qua -> phải chọn lại
        return
    status, until = validate(payload.get("validity_status"), payload.get("valid_until"))
    if not _apply(db, doc, status, until, actor_id=principal.id, ctx=ctx, reason=None):
        doc.validity_updated_by, doc.validity_updated_at = principal.id, utcnow()  # đã khai báo (giữ nguyên giá trị)


def apply_review(
    db: Session, principal: Principal, doc: Document, payload: dict[str, Any], ctx: RequestContext
) -> None:
    """Kiểm duyệt viên xác nhận/sửa hiệu lực khi duyệt (quyền duyệt đã kiểm ở workflow); không commit."""
    if payload.get("validity_status") in (None, ""):
        return
    status, until = validate(payload["validity_status"], payload.get("valid_until"))
    _apply(db, doc, status, until, actor_id=principal.id, ctx=ctx, reason=(payload.get("comments") or None))


def set_initial(
    db: Session, doc: Document, status: ValidityStatus, until: date | None, *, actor_id: uuid.UUID, ctx: RequestContext
) -> None:
    """Nhập hàng loạt (P2-08, FR-19): khai báo hiệu lực từ manifest.csv cho tài liệu vừa tạo; commit."""
    _apply(db, doc, status, until, actor_id=actor_id, ctx=ctx, reason=None)
    db.commit()


# ---------------------------------------------------------------- Celery beat


def _send_email(to: str, subject: str, body: str) -> None:
    try:
        get_email_sender().send(to, subject, body)
    except Exception:  # noqa: BLE001 - email lỗi không chặn tác vụ (thông báo trong hệ thống vẫn có)
        log.warning("Gửi email nhắc hiệu lực thất bại tới %s", to, exc_info=True)


def expire_due(db: Session, now: date) -> int:
    docs = list(
        db.scalars(
            select(Document).where(
                Document.validity_status == ValidityStatus.EFFECTIVE_UNTIL,
                Document.valid_until < now,
            )
        ).all()
    )
    for doc in docs:
        until = doc.valid_until
        _apply(
            db,
            doc,
            ValidityStatus.EXPIRED,
            until,
            actor_id=None,
            ctx=SYSTEM_CONTEXT,
            reason=None,
            action="validity_expired",
        )
        doc.validity_updated_by = None
        if doc.owner_id and doc.lifecycle_status == LifecycleStatus.ACTIVE:
            get_notifier().notify(
                db,
                [doc.owner_id],
                title="Tài liệu đã hết hiệu lực",
                message=f"'{doc.title}' hết hiệu lực từ sau ngày {until:%d/%m/%Y}" if until else f"'{doc.title}'",
                type="validity.expired",
                link_url=f"/documents/{doc.id}",
            )
    return len(docs)


def remind_due(db: Session, now: date) -> int:
    limit = now + timedelta(days=settings.VALIDITY_REMIND_DAYS)
    docs = list(
        db.scalars(
            select(Document).where(
                Document.validity_status == ValidityStatus.EFFECTIVE_UNTIL,
                Document.lifecycle_status == LifecycleStatus.ACTIVE,
                Document.valid_until >= now,
                Document.valid_until <= limit,
                Document.owner_id.is_not(None),
            )
        ).all()
    )
    docs = [d for d in docs if d.validity_reminded_on != d.valid_until]
    emails = active_emails(db, {d.owner_id for d in docs if d.owner_id}) if email_enabled() else {}
    for doc in docs:
        if doc.owner_id is None or doc.valid_until is None:
            continue
        left = days_left(doc.valid_until, now)
        when = "hôm nay là ngày cuối" if left == 0 else f"còn {left} ngày"
        message = f"'{doc.title}' {label(str(doc.validity_status), doc.valid_until).lower()} ({when})"
        get_notifier().notify(
            db,
            [doc.owner_id],
            title="Tài liệu sắp hết hiệu lực",
            message=message,
            type="validity.expiring",
            link_url=f"/documents/{doc.id}",
        )
        to = emails.get(doc.owner_id)
        if to:
            link = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/documents/{doc.id}" if settings.PUBLIC_BASE_URL else ""
            _send_email(to, f"Tài liệu sắp hết hiệu lực: {doc.title}", f"{message}.\n{link}".strip())
        doc.validity_reminded_on = doc.valid_until
    return len(docs)


def run_scheduled() -> dict[str, int]:
    """Beat (VALIDITY_CHECK_INTERVAL_SECONDS, idempotent): chuyển hết hạn rồi nhắc trước hạn."""
    with SessionLocal() as db:
        now = today()
        expired = expire_due(db, now)
        reminded = remind_due(db, now)
        db.commit()
        return {"expired": expired, "reminded": reminded}
