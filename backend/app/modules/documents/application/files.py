"""File gốc và ảnh trang chỉ đi qua API có kiểm quyền (SDD mục 14): đường dẫn nội bộ chỉ
dùng ở server, không trả storage_key ra client."""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application.queries import ensure_can_view, get_page
from app.shared.context import Principal, RequestContext
from app.shared.errors import NotFoundError
from app.shared.storage import get_storage


def open_original(
    db: Session, principal: Principal, document_id: uuid.UUID, ctx: RequestContext
) -> tuple[Path, str, str]:
    doc = ensure_can_view(db, principal, document_id)  # D-08: mọi vai trò trong phạm vi xem; mỗi lượt tải ghi audit
    path = get_storage().path(doc.storage_key)
    record(
        db,
        action="download_document",
        module="documents",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
    )
    db.commit()
    return path, doc.file_name, doc.mime_type


def page_image_path(db: Session, principal: Principal, document_id: uuid.UUID, page_number: int) -> Path:
    ensure_can_view(db, principal, document_id)
    page = get_page(db, document_id, page_number)
    if not page.image_key:
        raise NotFoundError("Trang chưa có ảnh")
    return get_storage().path(page.image_key)
