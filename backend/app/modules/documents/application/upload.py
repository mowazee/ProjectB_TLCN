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
from app.modules.documents.infrastructure.merge import merge_to_pdf
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.application.create import create_ocr_job
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import AppError, PayloadTooLargeError, PermissionDeniedError, UnprocessableError
from app.shared.events import publish
from app.shared.storage import document_prefix, get_storage, original_key


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
    document_code: str | None = None,
    origin: dict[str, str] | None = None,
    merged_files: int | None = None,
    attachments: list[Any] | None = None,
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
    code = (document_code or "").strip() or None
    if code and len(code) > 100:
        raise UnprocessableError(
            "Số hiệu dài quá 100 ký tự", code="DOCUMENT_CODE_TOO_LONG", fields={"document_code": "too_long"}
        )
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
            document_code=code,
            file_name=name,
            storage_key=key,
            mime_type=info.mime_type,
            bytes=len(data),
            is_handwritten=is_handwritten,
        )
        db.add(doc)
        db.flush()
        job = create_ocr_job(db, doc.id, is_handwritten=is_handwritten, origin=origin)
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
                "document_code": code,
                "category_id": category_id,
                "category_source": str(source),
                "file_name": name,
                "bytes": len(data),
                "pages": info.pages,
                "job_id": str(job.id),
                "is_handwritten": is_handwritten,
                **({"merged_files": merged_files} if merged_files else {}),
            },
        )
        if attachments:  # FR-15 (v0.13): tài liệu đi kèm lưu cùng transaction
            from app.modules.documents.application.attachments import save_attachments

            save_attachments(db, principal, doc, attachments, ctx)
        publish(db, DocumentUploaded(doc.id, principal.id))
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_prefix(document_prefix(doc_id))  # file gốc + tài liệu đi kèm đã lưu
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
    attachments: list[Any] | None = None,
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
        attachments=attachments,
    )


def upload_merged(
    db: Session,
    principal: Principal,
    *,
    files: list[tuple[BinaryIO, str | None]],
    title: str | None,
    category_id: int | None,
    is_handwritten: bool,
    ctx: RequestContext,
    category_mode: str = "user",
    attachments: list[Any] | None = None,
    keep_originals: bool = False,
) -> tuple[Document, Any]:
    """FR-16 (SDD v0.13): nhiều ảnh/PDF theo thứ tự -> một PDF -> một tài liệu, một job OCR.

    Từng file kiểm như FR-03; một file lỗi thì từ chối cả yêu cầu, lỗi chỉ rõ tên file. Tổng dung lượng và tổng số
    trang theo MAX_UPLOAD_MB, MAX_PAGES; số file theo MAX_MERGE_FILES."""
    if not policies.can_upload(principal):
        raise PermissionDeniedError("Bạn không có quyền upload tài liệu")
    if len(files) > settings.MAX_MERGE_FILES:
        raise UnprocessableError(
            f"Gộp tối đa {settings.MAX_MERGE_FILES} file một lần", code="TOO_MANY_FILES", fields={"files": "too_many"}
        )
    names, parts = _check_parts([(filename, stream) for stream, filename in files])
    extra = list(attachments or [])
    if keep_originals:  # FR-16: giữ các file gốc riêng lẻ làm tài liệu đi kèm (FR-15)
        from app.modules.documents.application.attachments import IncomingFile

        extra = [IncomingFile(n, d) for n, (d, _) in zip(names, parts, strict=True)] + extra
    merged = merge_to_pdf(parts)
    first = names[0].rsplit(".", 1)[0]  # tên file gộp theo file đầu tiên
    return create_document_from_bytes(
        db,
        principal,
        data=merged,
        filename=f"{first}.pdf",
        title=title,
        category_id=category_id,
        is_handwritten=is_handwritten,
        ctx=ctx,
        category_mode=category_mode,
        merged_files=len(parts),
        attachments=extra,
    )


def _check_parts(files: list[tuple[str | None, BinaryIO | bytes]]) -> tuple[list[str], list[tuple[bytes, str]]]:
    """Kiểm từng file như FR-03 (lỗi kèm tên file) và tổng dung lượng; trả (tên, [(dữ liệu, đuôi)])."""
    parts: list[tuple[bytes, str]] = []
    names: list[str] = []
    total = 0
    for filename, src in files:
        name = file_inspector.safe_filename(filename)
        try:
            data = src if isinstance(src, bytes) else file_inspector.read_limited(src, settings.max_upload_bytes)
            info = file_inspector.inspect(data, name)
        except AppError as exc:
            raise type(exc)(f"{name}: {exc.message}", code=exc.code, fields={"files": name}) from exc
        total += len(data)
        if total > settings.max_upload_bytes:
            raise PayloadTooLargeError(
                f"Tổng dung lượng các file vượt quá {settings.MAX_UPLOAD_MB} MB", fields={"files": "too_large"}
            )
        parts.append((data, info.ext))
        names.append(name)
    return names, parts


def merge_files(files: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    """FR-16 dùng chung cho nhập hàng loạt: gộp các file (đã đọc) thành một PDF; trả (dữ liệu, tên file)."""
    if len(files) > settings.MAX_MERGE_FILES:
        raise UnprocessableError(f"Gộp tối đa {settings.MAX_MERGE_FILES} file một lần", code="TOO_MANY_FILES")
    names, parts = _check_parts([(n, d) for n, d in files])
    return merge_to_pdf(parts), names[0].rsplit(".", 1)[0] + ".pdf"
