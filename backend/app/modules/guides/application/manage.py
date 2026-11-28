"""Tài liệu hướng dẫn sử dụng (FR-21, v0.16): Admin tải lên, sửa tiêu đề/mô tả, xóa; mọi người dùng đã đăng nhập xem.

File lưu trong kho riêng `guides/<id><ext>` (không lộ storage_key), tải/xem qua endpoint có kiểm đăng nhập.
Mọi thao tác ghi của Admin ghi audit (upload_guide, update_guide, delete_guide).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.guides.domain.files import ALLOWED_TEXT, TYPES, GuideType, content_matches, extension, safe_name
from app.modules.guides.infrastructure.models import GuideDocument
from app.modules.users.application.queries import display_names
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import (
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
    UnprocessableError,
    UnsupportedMediaTypeError,
)
from app.shared.pagination import PageParams
from app.shared.storage import get_storage

PREFIX = "guides"


@dataclass
class GuideView:
    id: uuid.UUID
    title: str
    description: str | None
    file_name: str
    mime_type: str
    bytes: int
    inline: bool
    uploaded_by: str | None
    created_at: datetime
    updated_at: datetime


def _require_admin(actor: Principal) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được quản lý tài liệu hướng dẫn")


def _views(db: Session, rows: list[GuideDocument]) -> list[GuideView]:
    names = display_names(db, {r.uploaded_by for r in rows if r.uploaded_by})
    return [
        GuideView(
            r.id,
            r.title,
            r.description,
            r.file_name,
            r.mime_type,
            r.bytes,
            TYPES.get(extension(r.file_name), GuideType(r.mime_type, False)).inline,
            names.get(r.uploaded_by) if r.uploaded_by else None,
            r.created_at,
            r.updated_at,
        )
        for r in rows
    ]


def _snap(g: GuideDocument) -> dict[str, Any]:
    return {"title": g.title, "description": g.description, "file_name": g.file_name, "bytes": g.bytes}


def _clean_title(title: str | None, fallback: str) -> str:
    value = (title or "").strip() or Path(fallback).stem
    if len(value) > 255:
        raise UnprocessableError("Tiêu đề tối đa 255 ký tự", fields={"title": "too_long"})
    return value


def list_guides(db: Session, params: PageParams, q: str | None = None) -> tuple[list[GuideView], int]:
    stmt = select(GuideDocument)
    if q and q.strip():
        needle = q.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(GuideDocument.title).contains(needle, autoescape=True),
                func.lower(GuideDocument.description).contains(needle, autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(GuideDocument.created_at.desc(), GuideDocument.id)
            .offset(params.offset)
            .limit(params.page_size)
        ).all()
    )
    return _views(db, rows), total


def create_guide(
    db: Session,
    actor: Principal,
    *,
    file_name: str,
    stream: BinaryIO,
    title: str | None,
    description: str | None,
    ctx: RequestContext,
) -> GuideView:
    _require_admin(actor)
    name = safe_name(file_name)
    ext = extension(name)
    if ext not in TYPES:
        raise UnsupportedMediaTypeError(f"Chỉ nhận {ALLOWED_TEXT}", fields={"file": "type"})
    limit = settings.MAX_GUIDE_MB * 1024 * 1024
    data = stream.read(limit + 1)
    if not data:
        raise UnprocessableError("File rỗng", code="FILE_EMPTY", fields={"file": "empty"})
    if len(data) > limit:
        raise PayloadTooLargeError(f"File vượt quá {settings.MAX_GUIDE_MB} MB")
    if not content_matches(ext, data[:16]):
        raise UnsupportedMediaTypeError("Nội dung file không khớp phần mở rộng", code="EXTENSION_MISMATCH")
    guide = GuideDocument(
        id=uuid.uuid4(),
        title=_clean_title(title, name),
        description=(description or "").strip() or None,
        file_name=name,
        mime_type=TYPES[ext].mime,
        bytes=len(data),
        uploaded_by=actor.id,
    )
    guide.storage_key = f"{PREFIX}/{guide.id}{ext}"
    storage = get_storage()
    storage.save_bytes(guide.storage_key, data)
    try:
        db.add(guide)
        record(
            db,
            action="upload_guide",
            module="guides",
            actor_id=actor.id,
            ctx=ctx,
            entity_type="guide_document",
            entity_id=guide.id,
            after=_snap(guide),
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(guide.storage_key)
        raise
    return _views(db, [guide])[0]


def _get(db: Session, guide_id: uuid.UUID) -> GuideDocument:
    guide = db.get(GuideDocument, guide_id)
    if guide is None:
        raise NotFoundError("Không tìm thấy tài liệu hướng dẫn")
    return guide


def update_guide(
    db: Session, actor: Principal, guide_id: uuid.UUID, changes: dict[str, Any], ctx: RequestContext
) -> GuideView:
    _require_admin(actor)
    guide = _get(db, guide_id)
    before = _snap(guide)
    if "title" in changes:
        guide.title = _clean_title(changes["title"], guide.file_name)
    if "description" in changes:
        guide.description = (changes["description"] or "").strip() or None
    record(
        db,
        action="update_guide",
        module="guides",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="guide_document",
        entity_id=guide.id,
        before=before,
        after=_snap(guide),
    )
    db.commit()
    return _views(db, [guide])[0]


def delete_guide(db: Session, actor: Principal, guide_id: uuid.UUID, ctx: RequestContext) -> None:
    _require_admin(actor)
    guide = _get(db, guide_id)
    key = guide.storage_key
    record(
        db,
        action="delete_guide",
        module="guides",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="guide_document",
        entity_id=guide.id,
        before=_snap(guide),
    )
    db.delete(guide)
    db.commit()
    get_storage().delete(key)


def open_file(db: Session, guide_id: uuid.UUID) -> tuple[Path, str, str, bool]:
    """(đường dẫn file, tên tải về, mime, xem trực tiếp?) - mọi người dùng đã đăng nhập."""
    guide = _get(db, guide_id)
    path = get_storage().path(guide.storage_key)
    if not path.is_file():
        raise NotFoundError("File hướng dẫn không còn trong kho")
    inline = TYPES.get(extension(guide.file_name), GuideType(guide.mime_type, False)).inline
    return path, guide.file_name, guide.mime_type, inline
