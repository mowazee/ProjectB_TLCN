"""UC-01 Upload tài liệu (FR-03).

Kiểm file -> lưu private storage (khóa nội bộ) -> tạo documents (active) + processing_jobs
(OCR, queued) + audit trong CÙNG transaction -> sau commit gửi job sang hàng đợi và phát
DocumentUploaded. Lỗi storage: không có bản ghi, không có job. Lỗi DB: xóa file vừa lưu.
"""

import uuid
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.categories.application import manage as categories
from app.modules.documents.domain import policies
from app.modules.documents.domain.events import DocumentUploaded
from app.modules.documents.domain.lifecycle import CategorySource
from app.modules.documents.infrastructure import file_inspector
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.application.create import create_ocr_job
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import PermissionDeniedError, UnprocessableError
from app.shared.events import publish
from app.shared.storage import get_storage, original_key


def create_document_from_bytes(
    db: Session,
    principal: Principal,
    *,
    data: bytes,
    filename: str | None,
    title: str | None,
    category_id: int | None,
    is_handwritten: bool,
    ctx: RequestContext,
    audit_action: str = "upload_document",
    category_mode: str = "user",
) -> tuple[Document, Any]:
    """Dùng chung cho UC-01 và từng file của bulk import (UC-23 include UC-01).

    category_mode (D-10, v0.9): "user" = người dùng chọn category_id; "auto" = Danh mục gợi ý - tài liệu vào "Chưa
    phân loại" (category_source = pending), job CLASSIFY (P2-05) tự áp dụng sau OCR."""
    if not policies.can_upload(principal):
        raise PermissionDeniedError("Bạn không có quyền upload tài liệu")
    if category_mode == "auto":
        if "classification" not in settings.features_enabled:
            raise UnprocessableError(
                "Danh mục gợi ý cần bật tính năng phân loại tự động (P2-05)",
                code="CATEGORY_MODE_UNAVAILABLE",
                fields={"category_mode": "unavailable"},
            )
        category_id = categories.unclassified_id(db)
        source = CategorySource.PENDING
    else:
        if category_id is None:
            raise UnprocessableError("Hãy chọn danh mục", code="CATEGORY_REQUIRED", fields={"category_id": "required"})
        categories.require_active(db, category_id)
        source = CategorySource.USER
    name = file_inspector.safe_filename(filename)
    info = file_inspector.inspect(data, name)

    doc_id = uuid.uuid4()
    key = original_key(doc_id, info.ext)
    storage = get_storage()
    storage.save_bytes(key, data)  # StorageError -> dừng, DB chưa có gì
    try:
        doc = Document(
            id=doc_id,
            category_id=category_id,
            category_source=source,
            owner_id=principal.id,
            department_id=principal.department_id,
            title=(title or "").strip()[:255] or Path(name).stem[:255],
            file_name=name,
            storage_key=key,
            mime_type=info.mime_type,
            bytes=len(data),
            is_handwritten=is_handwritten,
        )
        db.add(doc)
        db.flush()
        job = create_ocr_job(db, doc.id, is_handwritten=is_handwritten)
        record(
            db,
            action=audit_action,
            module="documents",
            actor_id=principal.id,
            ctx=ctx,
            entity_type="document",
            entity_id=doc.id,
            document_id=doc.id,
            after={
                "title": doc.title,
                "category_id": category_id,
                "category_source": str(source),
                "file_name": name,
                "bytes": len(data),
                "pages": info.pages,
                "job_id": str(job.id),
                "is_handwritten": is_handwritten,
            },
        )
        publish(db, DocumentUploaded(doc.id, principal.id))
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return doc, job


def upload_document(
    db: Session,
    principal: Principal,
    *,
    stream: BinaryIO,
    filename: str | None,
    title: str | None,
    category_id: int | None,
    is_handwritten: bool,
    ctx: RequestContext,
    category_mode: str = "user",
) -> tuple[Document, Any]:
    data = file_inspector.read_limited(stream, settings.max_upload_bytes)
    return create_document_from_bytes(
        db,
        principal,
        data=data,
        filename=filename,
        title=title,
        category_id=category_id,
        is_handwritten=is_handwritten,
        ctx=ctx,
        category_mode=category_mode,
    )
