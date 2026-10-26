"""API truy vấn công khai của documents (Đặc tả đề tài v0.5 mục 4.3).

Mọi module (search, ocr, dashboard, P2, P3) dùng lại visible_document_ids() để lọc quyền và
các hàm ensure_* để kiểm quyền trên một tài liệu; không truy vấn bảng documents trực tiếp.
"""

import uuid
from typing import Any

from sqlalchemy import Select, and_, exists, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.modules.documents.domain import policies
from app.modules.documents.domain.lifecycle import ApprovalStatus, LifecycleStatus, PageOcrStatus, ShareMode
from app.modules.documents.infrastructure.models import Document, DocumentPage, DocumentShare
from app.shared.config import settings
from app.shared.context import APPROVER, Principal
from app.shared.errors import NotFoundError, PermissionDeniedError


def publication_required() -> bool:
    """D-02 (v0.7): VIEWER chỉ thấy tài liệu đã xuất bản khi có quy trình duyệt (cờ workflow bật)."""
    return "workflow" in settings.features_enabled


def scope_of(doc: Document) -> policies.DocScope:
    """Chỉ đọc document_shares khi tài liệu đã xuất bản (lúc đó chia sẻ mới có hiệu lực, D-09)."""
    required = publication_required()
    shares = doc.shares if required and doc.approval_status == ApprovalStatus.PUBLISHED else []
    return policies.DocScope(
        doc.owner_id,
        doc.department_id,
        str(doc.approval_status),
        required,
        str(doc.share_mode),
        frozenset(s.department_id for s in shares if s.department_id is not None),
        frozenset(s.user_id for s in shares if s.user_id is not None),
    )


def _department_clause(principal: Principal) -> Any:
    """Bản SQL của policies.in_department_scope (D-02): quản lý, duyệt, thùng rác, hàng đợi."""
    if principal.is_admin:
        return true()
    if policies.is_reader_only(principal) or principal.id is None:
        return false()
    own = Document.owner_id == principal.id
    if principal.department_id is not None:
        return or_(own, Document.department_id == principal.department_id)
    return own


def _shared_with(principal: Principal, *, department: bool) -> Any:
    target = (
        DocumentShare.department_id == principal.department_id if department else DocumentShare.user_id == principal.id
    )
    return exists().where(DocumentShare.document_id == Document.id, target)


def _audience_clause(principal: Principal) -> Any:
    """Bản SQL của policies.in_share_audience (D-09) - chỉ áp cho tài liệu đã xuất bản."""
    conds = [
        Document.owner_id == principal.id,
        Document.share_mode == ShareMode.PUBLIC,
        _shared_with(principal, department=False),
    ]
    dep = principal.department_id
    if dep is not None:
        if APPROVER in principal.roles:
            conds.append(Document.department_id == dep)
        conds.append(
            and_(
                Document.share_mode == ShareMode.INTERNAL,
                or_(Document.department_id == dep, _shared_with(principal, department=True)),
            )
        )
    return or_(*conds)


def _view_clause(principal: Principal) -> Any:
    """Bản SQL của policies.can_view (giữ hai bản khớp nhau; test_v08_sharing kiểm cả hai)."""
    if principal.is_admin:
        return true()
    reader = policies.is_reader_only(principal)
    if not publication_required():
        if reader:  # không có khái niệm xuất bản: VIEWER xem tài liệu cùng phòng ban
            if principal.department_id is None:
                return false()
            return Document.department_id == principal.department_id
        return _department_clause(principal)
    published = Document.approval_status == ApprovalStatus.PUBLISHED
    unpublished = false() if reader else _department_clause(principal)
    return or_(and_(published, _audience_clause(principal)), and_(~published, unpublished))


def _scope_clause(principal: Principal) -> Any:
    """Phạm vi xem; người chỉ đọc không thấy thùng rác (tài liệu đã xóa nằm ngoài phạm vi kể cả khi include_deleted)."""
    clause = _view_clause(principal)
    if policies.is_reader_only(principal):
        clause = and_(clause, Document.lifecycle_status == LifecycleStatus.ACTIVE)
    return clause


def visible_document_ids(
    principal: Principal, *, include_deleted: bool = False, category_id: int | None = None
) -> Select[tuple[uuid.UUID]]:
    """SELECT id các tài liệu người dùng được XEM (mặc định chỉ tài liệu active) - mở rộng theo chia sẻ (D-09)."""
    clause = _scope_clause(principal)
    if not include_deleted:
        clause = and_(clause, Document.lifecycle_status == LifecycleStatus.ACTIVE)
    if category_id is not None:
        clause = and_(clause, Document.category_id == category_id)
    return select(Document.id).where(clause)


def department_document_ids(principal: Principal, *, include_deleted: bool = False) -> Select[tuple[uuid.UUID]]:
    """SELECT id tài liệu thuộc phạm vi PHÒNG BAN (D-02) - không mở rộng theo chia sẻ: hàng đợi xử lý, duyệt mượn."""
    clause = _department_clause(principal)
    if not include_deleted:
        clause = and_(clause, Document.lifecycle_status == LifecycleStatus.ACTIVE)
    return select(Document.id).where(clause)


def shared_with_me_clause(principal: Principal) -> Any:
    """FR-13: tài liệu đã xuất bản người khác chia sẻ tới mình - được thêm đích danh (kể cả người cùng phòng ban),
    phòng ban mình được chọn ở chế độ Nội bộ, hoặc tài liệu Toàn hệ thống của phòng ban khác. Dùng kèm phạm vi xem."""
    if not publication_required() or principal.id is None:
        return false()
    not_mine = or_(Document.owner_id.is_(None), Document.owner_id != principal.id)
    reasons = [_shared_with(principal, department=False)]
    dep = principal.department_id
    if dep is not None:
        reasons.append(and_(Document.share_mode == ShareMode.INTERNAL, _shared_with(principal, department=True)))
        other_department = or_(Document.department_id.is_(None), Document.department_id != dep)
        reasons.append(and_(Document.share_mode == ShareMode.PUBLIC, other_department))
    else:
        reasons.append(Document.share_mode == ShareMode.PUBLIC)
    return and_(Document.approval_status == ApprovalStatus.PUBLISHED, not_mine, or_(*reasons))


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


def ensure_permission(db: Session, principal: Principal, document_id: uuid.UUID, permission: str) -> Document:
    """D-11: tài liệu xem được VÀ người dùng có quyền permission (policies.EDIT, REPROCESS, ...); 403 kèm lý do."""
    doc = ensure_can_view(db, principal, document_id)
    scope = scope_of(doc)
    if not policies.allowed(principal, scope, permission):
        raise PermissionDeniedError(policies.denial_message(principal, scope, permission))
    return doc


def ensure_can_edit(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    """SỬA (D-11): metadata, danh mục, OCR, trường trích xuất, vị trí lưu trữ."""
    return ensure_permission(db, principal, document_id, policies.EDIT)


def ensure_can_reprocess(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    """Chạy lại OCR / chạy lại job OCR lỗi (D-11): chủ sở hữu khi Nháp / Bị từ chối."""
    return ensure_permission(db, principal, document_id, policies.REPROCESS)


def ensure_can_cancel_job(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    return ensure_permission(db, principal, document_id, policies.CANCEL_JOB)


def ensure_can_review(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    """Duyệt, xuất bản, hủy xuất bản, duyệt mượn: Kiểm duyệt viên phòng ban của tài liệu (chia sẻ không mở)."""
    doc = db.get(Document, document_id)
    if doc is None or doc.lifecycle_status != LifecycleStatus.ACTIVE:
        raise NotFoundError("Không tìm thấy tài liệu")
    if not policies.can_review(principal, scope_of(doc)):
        raise PermissionDeniedError("Chỉ Kiểm duyệt viên phòng ban của tài liệu được thực hiện thao tác này")
    return doc


def can_edit(principal: Principal, doc: Document) -> bool:
    return policies.can_edit(principal, scope_of(doc))


def permissions(principal: Principal, doc: Document) -> list[str]:
    return policies.permissions(principal, scope_of(doc))


def is_owner(principal: Principal, doc: Document) -> bool:
    return policies.is_owner(principal, scope_of(doc))


def can_submit(principal: Principal, doc: Document) -> bool:
    return policies.can_submit(principal, scope_of(doc))


def can_withdraw(principal: Principal, doc: Document) -> bool:
    return policies.can_withdraw(principal, scope_of(doc))


def can_review(principal: Principal, doc: Document) -> bool:
    return policies.can_review(principal, scope_of(doc))


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
            Document.category_source,
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
            "category_source": str(r.category_source),
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


def count_by_department(db: Session) -> dict[int, int]:
    """FR-10: số tài liệu (kể cả trong thùng rác) của từng phòng ban - phòng ban còn tài liệu thì không xóa được."""
    rows = db.execute(
        select(Document.department_id, func.count(Document.id))
        .where(Document.department_id.isnot(None))
        .group_by(Document.department_id)
    ).all()
    return {int(dep): int(n) for dep, n in rows}
