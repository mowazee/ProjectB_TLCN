"""UC-11 Yêu cầu mượn hồ sơ, UC-16 Duyệt mượn và ghi nhận trả (P2-07).

Mọi chuyển trạng thái có audit và thông báo (notifications). Trùng thời gian với yêu cầu đã duyệt
của cùng hồ sơ -> 409 BORROW_OVERLAP; chuyển sai trạng thái -> 409 INVALID_TRANSITION.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.borrowing.application.locations import document_location_id
from app.modules.borrowing.domain.rules import (
    APPROVED,
    PENDING,
    TRANSITIONS,
    BorrowAction,
    is_overdue,
)
from app.modules.borrowing.infrastructure.models import BorrowRequest, StorageLocation
from app.modules.documents.application import queries as documents
from app.modules.users.application.queries import display_names, user_ids_with_roles
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import SessionLocal
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError, UnprocessableError
from app.shared.notify import get_notifier
from app.shared.pagination import PageParams

DECIDERS = ("APPROVER", "ADMIN")


def today() -> date:
    return datetime.now(settings.tz).date()


@dataclass
class BorrowView:
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str | None
    storage_location: str | None
    requester_id: uuid.UUID | None
    requester_name: str | None
    approver_id: uuid.UUID | None
    approver_name: str | None
    status: str
    from_date: date
    to_date: date
    purpose: str | None
    created_at: datetime
    is_overdue: bool


def _views(db: Session, rows: list[BorrowRequest]) -> list[BorrowView]:
    briefs = documents.document_brief(db, {r.document_id for r in rows})
    names = display_names(db, {u for r in rows for u in (r.requester_id, r.approver_id) if u})
    locs: dict[uuid.UUID, str | None] = {}
    for doc_id in {r.document_id for r in rows}:
        loc_id = document_location_id(db, doc_id)
        loc = db.get(StorageLocation, loc_id) if loc_id else None
        locs[doc_id] = f"{loc.code} - {loc.name}" if loc else None
    t = today()
    return [
        BorrowView(
            r.id,
            r.document_id,
            briefs.get(r.document_id, {}).get("title"),
            locs.get(r.document_id),
            r.requester_id,
            names.get(r.requester_id) if r.requester_id else None,
            r.approver_id,
            names.get(r.approver_id) if r.approver_id else None,
            r.status,
            r.from_date,
            r.to_date,
            r.purpose,
            r.created_at,
            is_overdue(r.status, r.to_date, t),
        )
        for r in rows
    ]


def _overlapping_approved(db: Session, req_doc: uuid.UUID, f: date, t: date, exclude: uuid.UUID | None) -> bool:
    stmt = select(BorrowRequest.id).where(
        BorrowRequest.document_id == req_doc,
        BorrowRequest.status == APPROVED,
        BorrowRequest.from_date <= t,
        BorrowRequest.to_date >= f,
    )
    if exclude is not None:
        stmt = stmt.where(BorrowRequest.id != exclude)
    return db.scalar(stmt.limit(1)) is not None


def _audit(
    db: Session, actor: Principal, req: BorrowRequest, action: str, before: str | None, ctx: RequestContext
) -> None:
    record(
        db,
        action=action,
        module="borrowing",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="borrow_request",
        entity_id=req.id,
        document_id=req.document_id,
        before={"status": before} if before else None,
        after={
            "status": req.status,
            "from_date": req.from_date.isoformat(),
            "to_date": req.to_date.isoformat(),
            "approver_id": str(req.approver_id) if req.approver_id else None,
        },
    )


def create_request(
    db: Session,
    principal: Principal,
    *,
    document_id: uuid.UUID,
    from_date: date,
    to_date: date,
    purpose: str | None,
    ctx: RequestContext,
) -> BorrowView:
    doc = documents.ensure_can_view(db, principal, document_id)
    if from_date > to_date:
        raise UnprocessableError("Ngày bắt đầu phải trước ngày kết thúc", fields={"to_date": "before_from_date"})
    if to_date < today():
        raise UnprocessableError("Thời gian mượn đã qua", fields={"to_date": "in_past"})
    if document_location_id(db, doc.id) is None:
        raise UnprocessableError("Hồ sơ chưa có vị trí lưu trữ bản cứng", code="NO_STORAGE_LOCATION")
    if _overlapping_approved(db, doc.id, from_date, to_date, None):
        raise ConflictError("Hồ sơ đã được duyệt cho mượn trong khoảng thời gian này", code="BORROW_OVERLAP")
    req = BorrowRequest(
        document_id=doc.id,
        requester_id=principal.id,
        status=PENDING,
        from_date=from_date,
        to_date=to_date,
        purpose=(purpose or "").strip() or None,
    )
    db.add(req)
    db.flush()
    _audit(db, principal, req, "create_borrow_request", None, ctx)
    recipients = [u for u in user_ids_with_roles(db, {"APPROVER"}, doc.department_id) if u != principal.id]
    if recipients:
        get_notifier().notify(
            db,
            recipients,
            title="Yêu cầu mượn hồ sơ mới",
            message=f"'{doc.title}' {from_date:%d/%m/%Y}-{to_date:%d/%m/%Y}",
            type="borrow.created",
        )
    db.commit()
    return _views(db, [req])[0]


def act(
    db: Session, principal: Principal, request_id: uuid.UUID, action: BorrowAction, ctx: RequestContext
) -> BorrowView:
    if not principal.has_any(*DECIDERS):
        raise PermissionDeniedError("Chỉ Kiểm duyệt viên hoặc Quản trị viên được thực hiện")
    req = db.scalar(select(BorrowRequest).where(BorrowRequest.id == request_id).with_for_update())
    if req is None:
        raise NotFoundError("Không tìm thấy yêu cầu mượn")
    documents.ensure_can_view(db, principal, req.document_id)
    expected, target = TRANSITIONS[action]
    if req.status != expected:
        raise ConflictError(
            f"Không thể '{action.value}' yêu cầu đang ở trạng thái '{req.status}'",
            code="INVALID_TRANSITION",
            details={"current_status": req.status, "action": action.value},
        )
    if action == BorrowAction.APPROVE and _overlapping_approved(
        db, req.document_id, req.from_date, req.to_date, req.id
    ):
        raise ConflictError("Đã có yêu cầu được duyệt trùng thời gian cho hồ sơ này", code="BORROW_OVERLAP")
    before = req.status
    req.status = target
    if action != BorrowAction.RETURN:
        req.approver_id = principal.id
    _audit(db, principal, req, f"borrow_{action.value}", before, ctx)
    if req.requester_id and req.requester_id != principal.id:
        title = {
            BorrowAction.APPROVE: "Yêu cầu mượn đã được duyệt",
            BorrowAction.REJECT: "Yêu cầu mượn bị từ chối",
            BorrowAction.RETURN: "Đã ghi nhận trả hồ sơ",
        }[action]
        brief = documents.document_brief(db, {req.document_id}).get(req.document_id, {})
        get_notifier().notify(
            db, [req.requester_id], title=title, message=f"'{brief.get('title', '')}'", type=f"borrow.{action.value}"
        )
    db.commit()
    return _views(db, [req])[0]


def list_requests(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    status: str | None = None,
    document_id: uuid.UUID | None = None,
    overdue: bool = False,
    mine: bool = False,
) -> tuple[list[BorrowView], int]:
    """Kiểm duyệt/Admin: yêu cầu của hồ sơ trong phạm vi quyền; người khác: yêu cầu của mình."""
    stmt = select(BorrowRequest)
    if mine or not principal.has_any(*DECIDERS):
        stmt = stmt.where(BorrowRequest.requester_id == principal.id)
    else:
        stmt = stmt.where(
            or_(
                BorrowRequest.document_id.in_(documents.visible_document_ids(principal)),
                BorrowRequest.requester_id == principal.id,
            )
        )
    if status:
        stmt = stmt.where(BorrowRequest.status == status)
    if document_id:
        stmt = stmt.where(BorrowRequest.document_id == document_id)
    if overdue:
        stmt = stmt.where(and_(BorrowRequest.status == APPROVED, BorrowRequest.to_date < today()))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(stmt.order_by(BorrowRequest.created_at.desc()).offset(params.offset).limit(params.page_size)).all()
    )
    return _views(db, rows), total


def remind_overdue() -> int:
    """Celery beat: nhắc người mượn khi quá to_date mà chưa trả (P2-07)."""
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(BorrowRequest).where(BorrowRequest.status == APPROVED, BorrowRequest.to_date < today())
            ).all()
        )
        briefs = documents.document_brief(db, {r.document_id for r in rows})
        for r in rows:
            if r.requester_id:
                get_notifier().notify(
                    db,
                    [r.requester_id],
                    title="Hồ sơ mượn đã quá hạn",
                    message=f"'{briefs.get(r.document_id, {}).get('title', '')}' hạn trả {r.to_date:%d/%m/%Y}",
                    type="borrow.overdue",
                )
        db.commit()
        return len(rows)


def dashboard_counts(db: Session, principal: Principal) -> dict[str, int]:
    base = select(func.count(BorrowRequest.id)).where(
        BorrowRequest.document_id.in_(documents.visible_document_ids(principal))
    )
    return {
        "borrow_pending": db.scalar(base.where(BorrowRequest.status == PENDING)) or 0,
        "borrow_overdue": db.scalar(base.where(BorrowRequest.status == APPROVED, BorrowRequest.to_date < today())) or 0,
    }
