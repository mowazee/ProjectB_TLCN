"""UC-03 OCR Editor (FR-05) và UC-05a xem trang.

- GET trả raw_text, effective_text, confidence (số), boxes và version hiện hành (base_version).
- Lưu: base_version khác version hiện hành -> 409; hai request cùng lúc bị
  UNIQUE(page_id, version) chặn -> 409. Text thô không bao giờ bị ghi đè.
- Lưu xong: cập nhật chỉ mục cùng transaction, audit edit_ocr, phát CorrectionSaved.
- Sửa OCR không đổi approval_status.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application import queries as documents
from app.modules.documents.domain.lifecycle import PageOcrStatus
from app.modules.ocr.application.queries import current_correction, latest_result
from app.modules.ocr.domain.events import CorrectionSaved
from app.modules.ocr.infrastructure.models import OcrCorrection
from app.modules.search.application.index import index_page
from app.shared.context import Principal, RequestContext
from app.shared.db import utcnow
from app.shared.errors import ConflictError, UnprocessableError
from app.shared.events import publish


@dataclass
class PageDetail:
    document_id: uuid.UUID
    page_number: int
    total_pages: int
    width: int
    height: int
    ocr_status: str
    engine_version: str | None
    is_text_layer: bool
    confidence: Decimal | None
    raw_text: str
    effective_text: str
    version: int
    edited_by: uuid.UUID | None
    edited_at: Any
    boxes: list[dict[str, Any]] = field(default_factory=list)
    can_edit: bool = False


def get_page_detail(db: Session, principal: Principal, document_id: uuid.UUID, page_number: int) -> PageDetail:
    doc = documents.ensure_can_view(db, principal, document_id)
    page = documents.get_page(db, document_id, page_number)
    result = latest_result(db, page.id)
    current = current_correction(db, page.id)
    raw = result.raw_text if result else ""
    return PageDetail(
        document_id=doc.id,
        page_number=page.page_number,
        total_pages=documents.page_count(db, doc.id),
        width=page.width,
        height=page.height,
        ocr_status=str(page.ocr_status),
        engine_version=result.engine_version if result else None,
        is_text_layer=result.is_text_layer if result else False,
        confidence=result.confidence if result else None,
        raw_text=raw,
        effective_text=current.corrected_text if current else raw,
        version=current.version if current else 0,
        edited_by=current.edited_by if current else None,
        edited_at=current.edited_at if current else None,
        boxes=list(result.boxes or []) if result else [],
        can_edit=documents.can_manage(principal, doc),
    )


def save_correction(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    page_number: int,
    *,
    corrected_text: str,
    base_version: int,
    ctx: RequestContext,
    action: str = "edit_ocr",
    extra_after: dict[str, Any] | None = None,
) -> OcrCorrection:
    """action/extra_after cho phép rollback (P2-09) tạo một version mới mang nội dung cũ."""
    doc = documents.ensure_can_manage(db, principal, document_id)
    page = documents.get_page_for_update(db, document_id, page_number)  # khóa hàng (PostgreSQL)
    result = latest_result(db, page.id)
    if result is None or page.ocr_status not in (PageOcrStatus.COMPLETED, PageOcrStatus.NEEDS_REVIEW):
        raise ConflictError("Trang chưa có kết quả OCR để chỉnh sửa", code="OCR_NOT_READY")
    current = current_correction(db, page.id)
    current_version = current.version if current else 0
    if base_version != current_version:
        raise ConflictError(
            "Trang đã được người khác cập nhật. Vui lòng tải bản mới nhất.",
            code="VERSION_CONFLICT",
            details={"current_version": current_version, "base_version": base_version},
        )
    current_text = current.corrected_text if current else result.raw_text
    if corrected_text == current_text:
        raise UnprocessableError("Nội dung không thay đổi", code="NO_CHANGES")
    correction = OcrCorrection(
        page_id=page.id,
        edited_by=principal.id,
        version=current_version + 1,
        base_version=base_version,
        corrected_text=corrected_text,
        edited_at=utcnow(),
    )
    db.add(correction)
    documents.set_page_status(page, PageOcrStatus.COMPLETED)  # đã được người dùng rà soát
    index_page(db, page.id, corrected_text)
    record(
        db,
        action=action,
        module="ocr",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="page",
        entity_id=page.id,
        document_id=doc.id,
        before={"version": current_version, "text": current_text, "page_number": page_number},
        after={
            "version": correction.version,
            "text": corrected_text,
            "page_number": page_number,
            **(extra_after or {}),
        },
    )
    publish(db, CorrectionSaved(doc.id, page.id, page_number, correction.version))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Trang vừa được người khác cập nhật. Vui lòng tải bản mới nhất.", code="VERSION_CONFLICT"
        ) from exc
    return correction
