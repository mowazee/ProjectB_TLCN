"""UC-05 Quản lý tài liệu, UC-05b Thùng rác/khôi phục (FR-07, D-05)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.categories.application import manage as categories
from app.modules.documents.application.queries import (
    _scope_clause,
    can_manage,
    ensure_can_manage,
    ensure_can_view,
    scope_of,
)
from app.modules.documents.domain import policies
from app.modules.documents.domain.events import DocumentDeleted, DocumentRestored
from app.modules.documents.domain.lifecycle import (
    ApprovalStatus,
    LifecycleStatus,
    PageOcrStatus,
    can_restore_at,
    restore_deadline,
)
from app.modules.documents.infrastructure.models import Document, DocumentPage
from app.modules.jobs.application import queries as jobs
from app.modules.users.application.queries import display_names
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import aware, utcnow
from app.shared.errors import GoneError, NotFoundError, PermissionDeniedError
from app.shared.events import publish
from app.shared.pagination import PageParams


@dataclass
class DocumentView:
    """Dữ liệu trả ra API: không có storage_key (SDD mục 7)."""

    doc: Document
    category_name: str | None
    owner_name: str | None
    total_pages: int = 0
    needs_review_pages: int = 0
    job_status: str | None = None
    can_edit: bool = False
    job_id: uuid.UUID | None = None

    @property
    def restore_deadline(self) -> datetime | None:
        return restore_deadline(aware(self.doc.deleted_at), settings.SOFT_DELETE_RETENTION_DAYS)


def _snapshot(doc: Document) -> dict[str, Any]:
    return {
        "title": doc.title,
        "category_id": doc.category_id,
        "document_code": doc.document_code,
        "is_handwritten": doc.is_handwritten,
        "lifecycle_status": str(doc.lifecycle_status),
    }


def snapshot(db: Session, document_id: uuid.UUID) -> dict[str, Any]:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Không tìm thấy tài liệu")
    return _snapshot(doc)


def build_views(db: Session, principal: Principal, docs: list[Document]) -> list[DocumentView]:
    ids = [d.id for d in docs]
    cats = categories.names(db, {d.category_id for d in docs})
    owners = display_names(db, {d.owner_id for d in docs if d.owner_id})
    job_map = jobs.latest_job_map(db, ids)
    page_counts: dict[uuid.UUID, dict[str, int]] = {}
    if ids:
        for doc_id, st, n in db.execute(
            select(DocumentPage.document_id, DocumentPage.ocr_status, func.count(DocumentPage.id))
            .where(DocumentPage.document_id.in_(ids))
            .group_by(DocumentPage.document_id, DocumentPage.ocr_status)
        ).all():
            page_counts.setdefault(doc_id, {})[str(st)] = n
    views = []
    for d in docs:
        counts = page_counts.get(d.id, {})
        views.append(
            DocumentView(
                doc=d,
                category_name=cats.get(d.category_id),
                owner_name=owners.get(d.owner_id) if d.owner_id else None,
                total_pages=sum(counts.values()),
                needs_review_pages=counts.get(PageOcrStatus.NEEDS_REVIEW.value, 0),
                job_status=job_map[d.id][1] if d.id in job_map else None,
                can_edit=can_manage(principal, d),
                job_id=job_map[d.id][0] if d.id in job_map else None,
            )
        )
    return views


def list_documents(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    q: str | None = None,
    category_id: int | None = None,
    status: str | None = None,
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE,
    approval_status: ApprovalStatus | None = None,
) -> tuple[list[DocumentView], int]:
    """status: trạng thái job OCR mới nhất (queued/processing/completed/failed) hoặc
    'needs_review' (có trang cần xem lại). lifecycle_status=deleted là thùng rác. approval_status: FR-07 (v0.7)."""
    stmt = select(Document).where(_scope_clause(principal), Document.lifecycle_status == lifecycle_status)
    if q:
        stmt = stmt.where(func.lower(Document.title).contains(q.strip().lower(), autoescape=True))
    if category_id is not None:
        stmt = stmt.where(Document.category_id == category_id)
    if approval_status is not None:
        stmt = stmt.where(Document.approval_status == approval_status)
    if status == PageOcrStatus.NEEDS_REVIEW.value:
        stmt = stmt.where(
            select(DocumentPage.id)
            .where(DocumentPage.document_id == Document.id, DocumentPage.ocr_status == PageOcrStatus.NEEDS_REVIEW)
            .exists()
        )
    elif status:
        latest = jobs.latest_status_subquery()
        stmt = stmt.join(latest, latest.c.document_id == Document.id).where(latest.c.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = Document.deleted_at.desc() if lifecycle_status == LifecycleStatus.DELETED else Document.created_at.desc()
    docs = list(db.scalars(stmt.order_by(order).offset(params.offset).limit(params.page_size)).all())
    return build_views(db, principal, docs), total


def get_document_view(db: Session, principal: Principal, document_id: uuid.UUID) -> DocumentView:
    doc = ensure_can_view(db, principal, document_id)
    return build_views(db, principal, [doc])[0]


def update_document(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    changes: dict[str, Any],
    ctx: RequestContext,
    *,
    action: str = "update_document",
    extra_after: dict[str, Any] | None = None,
) -> Document:
    """Sửa metadata (tên, danh mục, số hiệu, chữ viết tay). Dùng lại cho P2-05 và P2-09."""
    doc = ensure_can_manage(db, principal, document_id)
    before = _snapshot(doc)
    if changes.get("title"):
        doc.title = str(changes["title"]).strip()[:255]
    if changes.get("category_id") is not None and changes["category_id"] != doc.category_id:
        categories.require_active(db, int(changes["category_id"]))
        doc.category_id = int(changes["category_id"])
    if "document_code" in changes:
        doc.document_code = (changes["document_code"] or "").strip() or None
    if changes.get("is_handwritten") is not None:
        doc.is_handwritten = bool(changes["is_handwritten"])
    after = _snapshot(doc)
    if before != after:
        record(
            db,
            action=action,
            module="documents",
            actor_id=principal.id,
            ctx=ctx,
            entity_type="document",
            entity_id=doc.id,
            document_id=doc.id,
            before=before,
            after={**after, **(extra_after or {})},
        )
        db.commit()
        db.refresh(doc)
    return doc


def soft_delete(db: Session, principal: Principal, document_id: uuid.UUID, ctx: RequestContext) -> None:
    """Xóa mềm: lifecycle_status=deleted + deleted_at; job đang chờ kết thúc; vào thùng rác."""
    doc = ensure_can_manage(db, principal, document_id)
    before = _snapshot(doc)
    doc.lifecycle_status = LifecycleStatus.DELETED
    doc.deleted_at = utcnow()
    stopped = jobs.fail_pending_jobs(db, doc.id, "DOCUMENT_DELETED")
    record(
        db,
        action="delete_document",
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        before=before,
        after={**_snapshot(doc), "stopped_jobs": stopped},
    )
    publish(db, DocumentDeleted(doc.id))
    db.commit()


def restore(db: Session, principal: Principal, document_id: uuid.UUID, ctx: RequestContext) -> Document:
    """UC-05b: khôi phục trong hạn SOFT_DELETE_RETENTION_DAYS; quá hạn 410; đã purge 404."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Không tìm thấy tài liệu (có thể đã bị xóa cứng)")
    if not policies.can_manage(principal, scope_of(doc)):
        raise PermissionDeniedError("Bạn không có quyền khôi phục tài liệu này")
    if doc.lifecycle_status != LifecycleStatus.DELETED:
        return doc
    if not can_restore_at(aware(doc.deleted_at), settings.SOFT_DELETE_RETENTION_DAYS, utcnow()):
        raise GoneError("Đã quá thời hạn khôi phục", code="RESTORE_EXPIRED")
    before = _snapshot(doc)
    doc.lifecycle_status = LifecycleStatus.ACTIVE
    doc.deleted_at = None
    record(
        db,
        action="restore_document",
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        before=before,
        after=_snapshot(doc),
    )
    publish(db, DocumentRestored(doc.id))
    db.commit()
    return doc


def get_trashed_scope_check(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Không tìm thấy tài liệu")
    if not policies.can_view(principal, scope_of(doc)):
        raise PermissionDeniedError("Bạn không có quyền truy cập tài liệu này")
    return doc
