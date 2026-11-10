"""FR-15 (SDD v0.13): tài liệu đi kèm (bộ hồ sơ) và tải cả bộ (.zip).

- Xem, tải: theo phạm vi xem của tài liệu chính (D-02, D-09). Thêm, xóa: theo quyền SỬA (D-11).
- Không OCR, không tìm kiếm nội dung; file nằm trong thư mục của tài liệu nên xóa cứng (purge) xóa luôn.
- Mỗi lượt thêm, xóa, tải ghi audit (add_attachment, delete_attachment, download_attachment, download_bundle).
"""

import tempfile
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application.queries import ensure_can_edit, ensure_can_view
from app.modules.documents.domain.attachments import AttachmentRejected, classify
from app.modules.documents.infrastructure import file_inspector
from app.modules.documents.infrastructure.models import Document, DocumentAttachment
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import (
    InvalidInputError,
    NotFoundError,
    PayloadTooLargeError,
    UnprocessableError,
    UnsupportedMediaTypeError,
)
from app.shared.storage import attachment_key, get_storage

MB = 1024 * 1024


@dataclass
class IncomingFile:
    filename: str | None
    data: bytes


def read_upload(stream: BinaryIO, filename: str | None) -> IncomingFile:
    name = file_inspector.safe_filename(filename)
    try:
        data = file_inspector.read_limited(stream, settings.MAX_ATTACHMENT_MB * MB)
    except PayloadTooLargeError as exc:
        raise PayloadTooLargeError(
            f"{name}: vượt quá {settings.MAX_ATTACHMENT_MB} MB", code=exc.code, fields={"attachments": name}
        ) from exc
    return IncomingFile(name, data)


def list_attachments(db: Session, principal: Principal, document_id: uuid.UUID) -> list[DocumentAttachment]:
    ensure_can_view(db, principal, document_id)
    return _list(db, document_id)


def _list(db: Session, document_id: uuid.UUID) -> list[DocumentAttachment]:
    return list(
        db.scalars(
            select(DocumentAttachment)
            .where(DocumentAttachment.document_id == document_id)
            .order_by(DocumentAttachment.created_at, DocumentAttachment.file_name)
        ).all()
    )


def save_attachments(
    db: Session,
    principal: Principal,
    doc: Document,
    files: list[IncomingFile],
    ctx: RequestContext,
    *,
    action: str = "add_attachment",
) -> list[DocumentAttachment]:
    """Kiểm giới hạn và loại file, lưu storage + bản ghi + audit. Không commit (dùng chung với upload).

    Lỗi một file → từ chối cả lô; file đã lưu được dọn (gọi rollback_files khi transaction lỗi)."""
    if not files:
        return []
    existing = db.execute(
        select(func.count(), func.coalesce(func.sum(DocumentAttachment.bytes), 0)).where(
            DocumentAttachment.document_id == doc.id
        )
    ).one()
    count, total = int(existing[0]), int(existing[1])
    if count + len(files) > settings.MAX_ATTACHMENTS:
        raise UnprocessableError(
            f"Mỗi tài liệu có tối đa {settings.MAX_ATTACHMENTS} tài liệu đi kèm",
            code="TOO_MANY_ATTACHMENTS",
            fields={"attachments": "too_many"},
        )
    total += sum(len(f.data) for f in files)
    if total > settings.MAX_BUNDLE_MB * MB:
        raise PayloadTooLargeError(
            f"Tổng dung lượng tài liệu đi kèm vượt quá {settings.MAX_BUNDLE_MB} MB", fields={"attachments": "too_large"}
        )
    checked = []
    for f in files:
        name = f.filename or "file"
        try:
            ext, mime = classify(name, f.data)
        except AttachmentRejected as exc:
            err = (
                UnsupportedMediaTypeError
                if exc.code in ("UNSUPPORTED_TYPE", "EXTENSION_MISMATCH")
                else InvalidInputError
            )
            raise err(f"{name}: {exc}", code=exc.code, fields={"attachments": name}) from exc
        checked.append((f, ext, mime))
    storage = get_storage()
    saved: list[DocumentAttachment] = []
    keys: list[str] = []
    try:
        for f, ext, mime in checked:
            att_id = uuid.uuid4()
            key = attachment_key(doc.id, att_id, ext)
            storage.save_bytes(key, f.data)
            keys.append(key)
            att = DocumentAttachment(
                id=att_id,
                document_id=doc.id,
                file_name=f.filename or f"file{ext}",
                storage_key=key,
                mime_type=mime,
                bytes=len(f.data),
                uploaded_by=principal.id,
            )
            db.add(att)
            saved.append(att)
        db.flush()
    except Exception:
        for key in keys:
            storage.delete(key)
        raise
    record(
        db,
        action=action,
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        after={"attachments": [{"id": str(a.id), "file_name": a.file_name, "bytes": a.bytes} for a in saved]},
    )
    return saved


def add_attachments(
    db: Session, principal: Principal, document_id: uuid.UUID, files: list[IncomingFile], ctx: RequestContext
) -> list[DocumentAttachment]:
    doc = ensure_can_edit(db, principal, document_id)  # D-11: thêm tài liệu đi kèm là thao tác SỬA
    if not files:
        raise UnprocessableError("Hãy chọn file", code="FILE_REQUIRED", fields={"attachments": "required"})
    saved: list[DocumentAttachment] = []
    try:
        saved = save_attachments(db, principal, doc, files, ctx)
        db.commit()
    except Exception:
        db.rollback()
        for att in saved:
            get_storage().delete(att.storage_key)
        raise
    return saved


def _get(db: Session, document_id: uuid.UUID, attachment_id: uuid.UUID) -> DocumentAttachment:
    att = db.get(DocumentAttachment, attachment_id)
    if att is None or att.document_id != document_id:
        raise NotFoundError("Không tìm thấy tài liệu đi kèm")
    return att


def delete_attachment(
    db: Session, principal: Principal, document_id: uuid.UUID, attachment_id: uuid.UUID, ctx: RequestContext
) -> None:
    doc = ensure_can_edit(db, principal, document_id)
    att = _get(db, doc.id, attachment_id)
    key, snap = att.storage_key, {"id": str(att.id), "file_name": att.file_name, "bytes": att.bytes}
    db.delete(att)
    record(
        db,
        action="delete_attachment",
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        before=snap,
    )
    db.commit()
    get_storage().delete(key)


def open_attachment(
    db: Session, principal: Principal, document_id: uuid.UUID, attachment_id: uuid.UUID, ctx: RequestContext
) -> tuple[Path, str, str]:
    doc = ensure_can_view(db, principal, document_id)
    att = _get(db, doc.id, attachment_id)
    record(
        db,
        action="download_attachment",
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        after={"attachment_id": str(att.id), "file_name": att.file_name},
    )
    db.commit()
    return get_storage().path(att.storage_key), att.file_name, att.mime_type


def _unique(name: str, used: set[str]) -> str:
    stem, ext = PurePath(name).stem, PurePath(name).suffix
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem} ({n}){ext}"
    used.add(candidate.lower())
    return candidate


def bundle(db: Session, principal: Principal, document_id: uuid.UUID, ctx: RequestContext) -> tuple[Path, str]:
    """Tải cả bộ: file gốc + tài liệu đi kèm (thư mục "di-kem/"). Trả (đường dẫn file zip tạm, tên tải về)."""
    doc = ensure_can_view(db, principal, document_id)
    items = _list(db, doc.id)
    storage = get_storage()
    tmp = tempfile.NamedTemporaryFile(prefix="bundle-", suffix=".zip", delete=False)  # noqa: SIM115
    tmp.close()
    used: set[str] = set()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(storage.path(doc.storage_key), _unique(file_inspector.safe_filename(doc.file_name), used))
        for att in items:
            z.write(
                storage.path(att.storage_key), "di-kem/" + _unique(file_inspector.safe_filename(att.file_name), used)
            )
    record(
        db,
        action="download_bundle",
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        after={"attachments": len(items)},
    )
    db.commit()
    stem = file_inspector.safe_filename(doc.title or PurePath(doc.file_name).stem)
    return Path(tmp.name), f"{PurePath(stem).stem or 'ho-so'}.zip"


def iter_and_remove(path: Path, chunk: int = 64 * 1024) -> Iterator[bytes]:
    """Stream file zip tạm rồi xóa."""
    try:
        with path.open("rb") as f:
            while data := f.read(chunk):
                yield data
    finally:
        path.unlink(missing_ok=True)
