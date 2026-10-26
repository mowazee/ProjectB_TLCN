"""UC-14 Gửi duyệt, UC-13 Duyệt/Từ chối, UC-15 Xuất bản/Hủy xuất bản (P2-01).

Mỗi lần chuyển: kiểm quyền (vai trò + phạm vi tài liệu) -> kiểm state machine (409) ->
compare-and-set documents.approval_status -> ghi document_approvals + audit + thông báo, cùng
một transaction. Sửa OCR không đổi approval_status (lõi không gọi module này).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application import queries as documents
from app.modules.users.application.queries import display_names, user_ids_with_roles
from app.modules.workflow.domain.state_machine import (
    ACTION_ROLES,
    OWNER_ACTIONS,
    PENDING,
    Action,
    InvalidTransition,
    allowed_actions,
    next_status,
)
from app.modules.workflow.infrastructure.models import DocumentApproval
from app.shared.context import Principal, RequestContext
from app.shared.db import aware, utcnow
from app.shared.errors import ConflictError, PermissionDeniedError, UnprocessableError
from app.shared.notify import get_notifier
from app.shared.pagination import PageParams

NOTIFY_TITLES = {
    Action.SUBMIT: "Tài liệu chờ duyệt",
    Action.APPROVE: "Tài liệu đã được duyệt",
    Action.REJECT: "Tài liệu bị từ chối",
    Action.PUBLISH: "Tài liệu đã xuất bản",
    Action.UNPUBLISH: "Tài liệu đã hủy xuất bản",
    Action.WITHDRAW: "Tài liệu đã được rút lại",
    Action.RETURN: "Tài liệu được trả lại để chỉnh sửa",
}


@dataclass
class ApprovalEntry:
    id: uuid.UUID
    action: str
    comments: str | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    created_at: datetime


@dataclass
class ReviewItem:
    document_id: uuid.UUID
    title: str
    category_id: int
    submitted_by: str | None
    submitted_at: datetime | None


def _last_submitter(db: Session, document_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(
        select(DocumentApproval.approver_id)
        .where(DocumentApproval.document_id == document_id, DocumentApproval.action == Action.SUBMIT.value)
        .order_by(DocumentApproval.created_at.desc())
        .limit(1)
    )


def transition(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    action: Action,
    *,
    comments: str | None,
    ctx: RequestContext,
) -> str:
    """Thực hiện action; trả approval_status mới."""
    if not principal.roles & ACTION_ROLES[action]:
        raise PermissionDeniedError("Vai trò của bạn không được thực hiện thao tác này")
    # Gửi duyệt, rút lại: chủ sở hữu (D-11); duyệt/xuất bản/hủy/trả lại: Kiểm duyệt viên phòng ban của tài liệu - chia
    # sẻ (FR-13, v0.8) chỉ mở quyền xem nên Kiểm duyệt viên phòng khác được chia sẻ không hủy xuất bản được
    if action in OWNER_ACTIONS:
        doc = documents.ensure_can_view(db, principal, document_id)
        if not documents.is_owner(principal, doc):
            raise PermissionDeniedError("Chỉ người tải lên tài liệu mới gửi duyệt / rút lại được")
    else:
        doc = documents.ensure_can_review(db, principal, document_id)
    comments = (comments or "").strip() or None
    if action == Action.REJECT and not comments:
        raise UnprocessableError("Từ chối phải kèm lý do", fields={"comments": "required"})
    if action == Action.RETURN and not comments:
        raise UnprocessableError("Trả lại phải kèm ghi chú cho người tải lên", fields={"comments": "required"})
    current = str(doc.approval_status)
    try:
        step = next_status(action, current)
    except InvalidTransition as exc:
        raise ConflictError(
            str(exc), code="INVALID_TRANSITION", details={"current_status": current, "action": action.value}
        ) from exc
    if not documents.set_approval_status(db, doc.id, step.to_status, expected=step.from_status):
        raise ConflictError("Trạng thái tài liệu vừa được người khác thay đổi", code="INVALID_TRANSITION")
    # created_at tăng nghiêm ngặt theo tài liệu: đồng hồ hệ thống có thể trùng giá trị giữa hai thao tác liên tiếp
    last = aware(db.scalar(select(func.max(DocumentApproval.created_at)).where(DocumentApproval.document_id == doc.id)))
    now = utcnow()
    if last is not None and now <= last:
        now = last + timedelta(microseconds=1)
    db.add(
        DocumentApproval(
            document_id=doc.id, approver_id=principal.id, action=action.value, comments=comments, created_at=now
        )
    )
    record(
        db,
        action=f"approval_{action.value}",
        module="workflow",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        before={"approval_status": step.from_status},
        after={"approval_status": step.to_status, "comments": comments},
    )
    if action in OWNER_ACTIONS:  # gửi duyệt / rút lại: báo Kiểm duyệt viên phòng ban của tài liệu
        recipients = [u for u in user_ids_with_roles(db, {"APPROVER"}, doc.department_id) if u != principal.id]
    else:
        submitter = _last_submitter(db, doc.id) or doc.owner_id
        recipients = [submitter] if submitter and submitter != principal.id else []
    if recipients:
        message = f"'{doc.title}'" + (f" - {comments}" if comments else "")
        link = "/reviews" if action == Action.SUBMIT else f"/documents/{doc.id}"  # trả lại: chủ sở hữu mở tài liệu
        get_notifier().notify(
            db,
            recipients,
            title=NOTIFY_TITLES[action],
            message=message,
            type=f"approval.{action.value}",
            link_url=link,
        )
    db.commit()
    return step.to_status


def history(db: Session, principal: Principal, document_id: uuid.UUID) -> list[ApprovalEntry]:
    documents.ensure_can_view(db, principal, document_id)
    rows = list(
        db.scalars(
            select(DocumentApproval)
            .where(DocumentApproval.document_id == document_id)
            .order_by(DocumentApproval.created_at, DocumentApproval.id)
        ).all()
    )
    names = display_names(db, {r.approver_id for r in rows if r.approver_id})
    return [
        ApprovalEntry(
            r.id, r.action, r.comments, r.approver_id, names.get(r.approver_id) if r.approver_id else None, r.created_at
        )
        for r in rows
    ]


def state(db: Session, principal: Principal, document_id: uuid.UUID) -> dict[str, Any]:
    doc = documents.ensure_can_view(db, principal, document_id)
    current = str(doc.approval_status)
    owner = documents.is_owner(principal, doc)
    reviewer = documents.can_review(principal, doc)  # FR-13: người được chia sẻ không duyệt/xuất bản
    actions = [
        a for a in allowed_actions(current, principal.roles) if (owner if Action(a) in OWNER_ACTIONS else reviewer)
    ]
    return {"approval_status": current, "allowed_actions": actions}


def review_queue(db: Session, principal: Principal, params: PageParams) -> tuple[list[ReviewItem], int]:
    """GET /api/reviews: tài liệu pending_review trong phạm vi quyền (Kiểm duyệt/Admin)."""
    if not principal.has_any("APPROVER", "ADMIN"):
        raise PermissionDeniedError("Chỉ Kiểm duyệt viên hoặc Quản trị viên xem hàng chờ duyệt")
    ids_stmt = documents.documents_with_approval(principal, PENDING)  # type: ignore[arg-type]
    total = db.scalar(select(func.count()).select_from(ids_stmt.subquery())) or 0
    last_submit = (
        select(
            DocumentApproval.document_id,
            func.max(DocumentApproval.created_at).label("submitted_at"),
        )
        .where(DocumentApproval.action == Action.SUBMIT.value)
        .group_by(DocumentApproval.document_id)
        .subquery()
    )
    rows = db.execute(
        select(last_submit.c.document_id, last_submit.c.submitted_at)
        .where(last_submit.c.document_id.in_(ids_stmt))
        .order_by(last_submit.c.submitted_at)
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    ids = [r.document_id for r in rows]
    briefs = documents.document_brief(db, set(ids))
    submitters = {doc_id: _last_submitter(db, doc_id) for doc_id in ids}
    names = display_names(db, {u for u in submitters.values() if u})
    items = []
    for r in rows:
        b = briefs.get(r.document_id)
        if b is None:
            continue
        sub = submitters.get(r.document_id)
        items.append(
            ReviewItem(r.document_id, b["title"], b["category_id"], names.get(sub) if sub else None, r.submitted_at)
        )
    return items, total


def pending_count(db: Session, principal: Principal) -> dict[str, int]:
    """Dashboard contributor: số tài liệu chờ duyệt trong phạm vi quyền."""
    stmt = documents.documents_with_approval(principal, PENDING)  # type: ignore[arg-type]
    return {"documents_pending_review": db.scalar(select(func.count()).select_from(stmt.subquery())) or 0}
