"""API truy vấn công khai của documents (Đặc tả đề tài v0.5 mục 4.3).

Mọi module (search, ocr, dashboard, P2, P3) dùng lại visible_document_ids() để lọc quyền và
các hàm ensure_* để kiểm quyền trên một tài liệu; không truy vấn bảng documents trực tiếp.
"""

import uuid
from typing import Any

from sqlalchemy import Select, and_, false, or_, select, true
from sqlalchemy.orm import Session

from app.modules.documents.domain import policies
from app.modules.documents.domain.lifecycle import ApprovalStatus, LifecycleStatus, PageOcrStatus
from app.modules.documents.infrastructure.models import Document, DocumentPage
from app.shared.context import Principal
from app.shared.errors import NotFoundError, PermissionDeniedError


def scope_of(doc: Document) -> policies.DocScope:
    return policies.DocScope(doc.owner_id, doc.department_id)


def _scope_clause(principal: Principal) -> Any:
    if principal.is_admin:
        return true()
    own = Document.owner_id == principal.id
    if principal.department_id is not None:
        return or_(own, Document.department_id == principal.department_id)
    return own if principal.id else false()


def visible_document_ids(
    principal: Principal, *, include_deleted: bool = False, category_id: int | None = None
) -> Select[tuple[uuid.UUID]]:
    """SELECT id các tài liệu người dùng được xem (mặc định chỉ tài liệu active)."""
    clause = _scope_clause(principal)
    if not include_deleted:
        clause = and_(clause, Document.lifecycle_status == LifecycleStatus.ACTIVE)
    if category_id is not None:
        clause = and_(clause, Document.category_id == category_id)
    return select(Document.id).where(clause)


def get_document(db: Session, document_id: uuid.UUID) -> Document | None:
    return db.get(Document, document_id)


def ensure_can_view(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    """404 nếu không tồn tại / đã xóa; 403 nếu ngoài phạm vi (UC-05a 2a)."""
    doc = db.get(Document, document_id)
    if doc is None or doc.lifecycle_status != LifecycleStatus.ACTIVE:
        raise NotFoundError("Không tìm thấy tài liệu")
    if not policies.can_view(principal, scope_of(doc)):
        raise PermissionDeniedError("Bạn không có quyền truy cập tài liệu này")
    return doc


def ensure_can_manage(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    doc = ensure_can_view(db, principal, document_id)
    if not policies.can_manage(principal, scope_of(doc)):
        raise PermissionDeniedError("Bạn không có quyền chỉnh sửa tài liệu này")
    return doc


def can_manage(principal: Principal, doc: Document) -> bool:
    return policies.can_manage(principal, scope_of(doc))


def is_active(db: Session, document_id: uuid.UUID) -> bool:
    doc = db.get(Document, document_id)
    return doc is not None and doc.lifecycle_status == LifecycleStatus.ACTIVE


# ---------------------------------------------------------------- trang (dùng bởi ocr, search, P2)
def get_page(db: Session, document_id: uuid.UUID, page_number: int) -> DocumentPage:
    page = db.scalar(
        select(DocumentPage).where(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number)
    )
    if page is None:
        raise NotFoundError("Không tìm thấy trang")
    return page


def get_page_for_update(db: Session, document_id: uuid.UUID, page_number: int) -> DocumentPage:
    page = db.scalar(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number)
        .with_for_update()
    )
    if page is None:
        raise NotFoundError("Không tìm thấy trang")
    return page


def list_pages(db: Session, document_id: uuid.UUID) -> list[DocumentPage]:
    return list(
        db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
        ).all()
    )


def page_count(db: Session, document_id: uuid.UUID) -> int:
    return len(list_pages(db, document_id))


def upsert_page(
    db: Session, document_id: uuid.UUID, page_number: int, *, image_key: str, width: int, height: int
) -> DocumentPage:
    """Worker OCR tạo/cập nhật trang (idempotent theo UNIQUE(document_id, page_number))."""
    page = db.scalar(
        select(DocumentPage).where(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number)
    )
    if page is None:
        page = DocumentPage(document_id=document_id, page_number=page_number)
        db.add(page)
    page.image_key, page.width, page.height = image_key, width, height
    db.flush()
    return page


def set_page_status(page: DocumentPage, status: PageOcrStatus) -> None:
    page.ocr_status = status


def set_approval_status(
    db: Session, document_id: uuid.UUID, status: ApprovalStatus | str, *, expected: str | None = None
) -> bool:
    """Dùng bởi workflow (P2-01): approval_status là cột của lõi, chỉ đổi qua hàm này.

    expected: compare-and-set - chỉ đổi khi trạng thái hiện tại đúng bằng expected (hai người duyệt
    cùng lúc thì một người nhận False). Trả True nếu đã đổi.
    """
    from sqlalchemy import update

    stmt = update(Document).where(Document.id == document_id)
    if expected is not None:
        stmt = stmt.where(Document.approval_status == expected)
    result = db.execute(
        stmt.values(approval_status=ApprovalStatus(status)).execution_options(synchronize_session="fetch")
    )
    return bool(getattr(result, "rowcount", 0))


def document_brief(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    if not ids:
        return {}
    rows = db.execute(
        select(
            Document.id,
            Document.title,
            Document.owner_id,
            Document.department_id,
            Document.approval_status,
            Document.category_id,
            Document.created_at,
        ).where(Document.id.in_(ids))
    ).all()
    return {
        r.id: {
            "title": r.title,
            "owner_id": r.owner_id,
            "department_id": r.department_id,
            "approval_status": str(r.approval_status),
            "category_id": r.category_id,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    }


def dashboard_counts(db: Session, principal: Principal) -> dict[str, Any]:
    """Số liệu cho dashboard trong phạm vi quyền (FR-08)."""
    from sqlalchemy import distinct, func

    ids = visible_document_ids(principal)
    documents = db.scalar(select(func.count()).select_from(ids.subquery())) or 0
    pages = {
        str(s): n
        for s, n in db.execute(
            select(DocumentPage.ocr_status, func.count(DocumentPage.id))
            .where(DocumentPage.document_id.in_(ids))
            .group_by(DocumentPage.ocr_status)
        ).all()
    }
    by_category = {
        c: n
        for c, n in db.execute(
            select(Document.category_id, func.count(Document.id))
            .where(Document.id.in_(ids))
            .group_by(Document.category_id)
        ).all()
    }
    review_docs = (
        db.scalar(
            select(func.count(distinct(DocumentPage.document_id))).where(
                DocumentPage.document_id.in_(ids), DocumentPage.ocr_status == PageOcrStatus.NEEDS_REVIEW
            )
        )
        or 0
    )
    return {
        "documents": documents,
        "pages_by_status": pages,
        "by_category": by_category,
        "documents_needs_review": review_docs,
    }


def documents_with_approval(principal: Principal, status: ApprovalStatus) -> Select[tuple[uuid.UUID]]:
    return visible_document_ids(principal).where(Document.approval_status == status)
