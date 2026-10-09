"""UC-21 Trích xuất trường (P2-04).

- OcrCompleted -> tạo job EXTRACT (event handler, chạy sau commit của worker OCR).
- run_extraction: text hiệu lực -> quy tắc theo danh mục -> upsert theo UNIQUE(document_id, field_name);
  trường người dùng đã xác nhận (is_verified) không bị ghi đè khi chạy lại.
- Người dùng xem, sửa và xác nhận từng trường; sửa/xác nhận có audit.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.categories.application import manage as categories
from app.modules.documents.application import queries as documents
from app.modules.extraction.domain import rules
from app.modules.extraction.infrastructure.models import DocumentExtractedField
from app.modules.jobs.application import queries as jobs
from app.modules.jobs.application.create import create_job
from app.modules.jobs.domain.model import JobError
from app.modules.ocr.application.queries import document_effective_text
from app.shared.context import Principal, RequestContext
from app.shared.db import SessionLocal
from app.shared.errors import ConflictError, NotFoundError

logger = logging.getLogger(__name__)
KIND = "EXTRACT"
MANUAL = "manual"


@dataclass
class FieldView:
    field_name: str
    label: str
    field_value: str | None
    extracted_method: str | None
    is_verified: bool


def _category_code(db: Session, category_id: int) -> str | None:
    try:
        return str(categories.snapshot(db, category_id)["code"])
    except NotFoundError:
        return None


def _rows(db: Session, document_id: uuid.UUID) -> dict[str, DocumentExtractedField]:
    return {
        f.field_name: f
        for f in db.scalars(select(DocumentExtractedField).where(DocumentExtractedField.document_id == document_id))
    }


# ---------------------------------------------------------------- job
def enqueue_extraction(evt: Any) -> None:
    """Event handler OcrCompleted (session riêng; job đang chạy thì bỏ qua)."""
    with SessionLocal() as db:
        try:
            create_job(db, kind=KIND, document_id=evt.document_id, queue="default")
            db.commit()
        except ConflictError:
            db.rollback()


def run_extraction(ctx: Any) -> None:
    db: Session = ctx.db
    doc = documents.get_document(db, ctx.document_id)
    if doc is None or not documents.is_active(db, ctx.document_id):
        raise JobError("DOCUMENT_DELETED", "Tài liệu đã bị xóa")
    pages = documents.list_pages(db, doc.id)
    text = document_effective_text(db, [p.id for p in pages])
    found = rules.extract(text, _category_code(db, doc.category_id))
    existing = _rows(db, doc.id)
    updated, kept = [], []
    for item in found:
        row = existing.get(item.name)
        if row is None:
            db.add(
                DocumentExtractedField(
                    document_id=doc.id, field_name=item.name, field_value=item.value, extracted_method=rules.METHOD
                )
            )
            updated.append(item.name)
        elif row.is_verified:
            kept.append(item.name)  # người dùng đã xác nhận: không ghi đè
        elif row.field_value != item.value:
            row.field_value, row.extracted_method = item.value, rules.METHOD
            updated.append(item.name)
    ctx.set_result({"fields_found": [f.name for f in found], "updated": updated, "kept_verified": kept})


# ---------------------------------------------------------------- API
def list_fields(db: Session, principal: Principal, document_id: uuid.UUID) -> tuple[list[FieldView], Any]:
    doc = documents.ensure_can_view(db, principal, document_id)
    labels = rules.field_labels(_category_code(db, doc.category_id))
    rows = _rows(db, doc.id)
    names = list(labels) + [n for n in rows if n not in labels]
    views = []
    for n in names:
        r = rows.get(n)
        views.append(
            FieldView(
                n,
                labels.get(n, n),
                r.field_value if r else None,
                r.extracted_method if r else None,
                bool(r and r.is_verified),
            )
        )
    return views, jobs.latest_job(db, doc.id, KIND)


def update_field(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    field_name: str,
    *,
    value: str | None,
    is_verified: bool,
    ctx: RequestContext,
) -> FieldView:
    doc = documents.ensure_can_manage(db, principal, document_id)
    labels = rules.field_labels(_category_code(db, doc.category_id))
    row = _rows(db, doc.id).get(field_name)
    if row is None and field_name not in labels:
        raise NotFoundError("Không có trường này cho danh mục của tài liệu")
    value = (value or "").strip() or None
    before = (
        {"field_value": row.field_value, "is_verified": row.is_verified, "extracted_method": row.extracted_method}
        if row
        else None
    )
    if row is None:
        row = DocumentExtractedField(document_id=doc.id, field_name=field_name, extracted_method=MANUAL)
        db.add(row)
    changed_value = before is None or before["field_value"] != value
    row.field_value = value
    row.is_verified = is_verified
    if changed_value:
        row.extracted_method = MANUAL
    db.flush()
    record(
        db,
        action="update_field" if changed_value else ("verify_field" if is_verified else "unverify_field"),
        module="extraction",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="extracted_field",
        entity_id=row.id,
        document_id=doc.id,
        before=before,
        after={
            "field_name": field_name,
            "field_value": value,
            "is_verified": is_verified,
            "extracted_method": row.extracted_method,
        },
    )
    db.commit()
    return FieldView(field_name, labels.get(field_name, field_name), value, row.extracted_method, is_verified)


def request_extraction(db: Session, principal: Principal, document_id: uuid.UUID, ctx: RequestContext) -> Any:
    doc = documents.ensure_can_manage(db, principal, document_id)
    job = create_job(db, kind=KIND, document_id=doc.id, queue="default")
    record(
        db,
        action="request_extraction",
        module="extraction",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        after={"job_id": str(job.id)},
    )
    db.commit()
    return job
