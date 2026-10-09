"""UC-08b Rollback thay đổi (P2-09): đưa metadata tài liệu, danh mục hoặc bản sửa OCR về
audit_logs.state_before bằng use case của lõi (tạo thay đổi mới, không xóa lịch sử).

- Tài liệu: documents.update_document(action="rollback_document").
- Danh mục: categories.update_category(action="rollback_category").
- OCR: editor.save_correction(action="rollback_ocr") tạo version mới mang nội dung cũ.
Nếu dữ liệu hiện tại khác state_after của dòng audit (đã bị sửa tiếp) -> 409 ROLLBACK_STALE
trừ khi Admin gửi confirm=true.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.application.queries import get_log
from app.modules.categories.application import manage as categories
from app.modules.documents.application import manage as documents
from app.modules.documents.application import queries as doc_queries
from app.modules.ocr.application import editor
from app.modules.ocr.application.queries import current_correction, get_effective_text
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, PermissionDeniedError, UnprocessableError

DOCUMENT_ACTIONS = {"update_document", "accept_category_suggestion", "rollback_document"}
CATEGORY_ACTIONS = {"update_category", "activate_category", "deactivate_category", "rollback_category"}
OCR_ACTIONS = {"edit_ocr", "rollback_ocr"}
SUPPORTED_ACTIONS = DOCUMENT_ACTIONS | CATEGORY_ACTIONS | OCR_ACTIONS

DOC_FIELDS = ("title", "category_id", "document_code", "is_handwritten")
CAT_FIELDS = ("name", "parent_id", "retention_period_years", "description", "is_active")


@dataclass
class RollbackPlan:
    log_id: int
    kind: str  # document | category | ocr
    supported: bool
    changed_since: bool
    current: dict[str, Any]
    target: dict[str, Any]


def _pick(d: dict[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
    d = d or {}
    return {k: d.get(k) for k in keys if k in d}


def plan(db: Session, actor: Principal, log_id: int) -> RollbackPlan:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được rollback")
    log = get_log(db, log_id)
    if str(log.result) != "success" or log.action not in SUPPORTED_ACTIONS or not log.state_before:
        return RollbackPlan(log_id, "unsupported", False, False, {}, {})
    if log.action in DOCUMENT_ACTIONS:
        if log.document_id is None:
            return RollbackPlan(log_id, "document", False, False, {}, {})
        current = _pick(documents.snapshot(db, log.document_id), DOC_FIELDS)
        target = _pick(log.state_before, DOC_FIELDS)
        changed = current != _pick(log.state_after, DOC_FIELDS)
        return RollbackPlan(log_id, "document", True, changed, current, target)
    if log.action in CATEGORY_ACTIONS:
        current = _pick(categories.snapshot(db, int(str(log.entity_id))), CAT_FIELDS)
        target = _pick(log.state_before, CAT_FIELDS)
        return RollbackPlan(log_id, "category", True, current != _pick(log.state_after, CAT_FIELDS), current, target)
    # OCR: so version hiện hành với version mà dòng audit tạo ra
    if log.document_id is None:
        return RollbackPlan(log_id, "ocr", False, False, {}, {})
    page_number = int((log.state_after or {}).get("page_number") or log.state_before.get("page_number") or 0)
    page = doc_queries.get_page(db, log.document_id, page_number)
    cur = current_correction(db, page.id)
    current = {
        "version": cur.version if cur else 0,
        "text": get_effective_text(db, page.id),
        "page_number": page_number,
    }
    target = {"text": log.state_before.get("text", ""), "page_number": page_number}
    changed = current["version"] != (log.state_after or {}).get("version")
    return RollbackPlan(log_id, "ocr", True, changed, current, target)


def execute(db: Session, actor: Principal, log_id: int, *, confirm: bool, ctx: RequestContext) -> RollbackPlan:
    p = plan(db, actor, log_id)
    if not p.supported:
        raise UnprocessableError("Dòng nhật ký này không hỗ trợ rollback", code="ROLLBACK_NOT_SUPPORTED")
    if p.changed_since and not confirm:
        raise ConflictError(
            "Dữ liệu đã được sửa tiếp sau thay đổi này. Xác nhận để vẫn rollback.",
            code="ROLLBACK_STALE",
            details={"current": p.current, "target": p.target},
        )
    log = get_log(db, log_id)
    extra = {"rollback_of": log_id}
    doc_id = log.document_id
    if p.kind in ("document", "ocr") and doc_id is None:  # plan() đã loại trường hợp này
        raise UnprocessableError("Dòng nhật ký không gắn tài liệu", code="ROLLBACK_NOT_SUPPORTED")
    if p.kind == "document" and doc_id is not None:
        if p.current == p.target:
            raise UnprocessableError("Dữ liệu hiện tại đã giống trạng thái trước", code="NO_CHANGES")
        documents.update_document(db, actor, doc_id, dict(p.target), ctx, action="rollback_document", extra_after=extra)
    elif p.kind == "category":
        if p.current == p.target:
            raise UnprocessableError("Dữ liệu hiện tại đã giống trạng thái trước", code="NO_CHANGES")
        cat_id = int(str(log.entity_id))
        categories.update_category(db, actor, cat_id, dict(p.target), ctx, action="rollback_category")
    elif doc_id is not None:
        editor.save_correction(
            db,
            actor,
            doc_id,
            int(p.target["page_number"]),
            corrected_text=str(p.target["text"]),
            base_version=int(p.current["version"]),
            ctx=ctx,
            action="rollback_ocr",
            extra_after=extra,
        )
    return p
