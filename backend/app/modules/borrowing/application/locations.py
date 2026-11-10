"""Kho lưu trữ hồ sơ bản cứng (P2-07): Admin quản lý; gán vị trí cho tài liệu.

D-12 (v0.13): Kho chung (KHO-CHUNG, is_virtual) là vị trí hệ thống cho tài liệu không có bản cứng, không sửa
được; documents.has_physical_copy ghi có/không/chưa khai báo. Khai báo bản cứng khi gửi duyệt (hook của
workflow); sau khi xuất bản, chủ sở hữu, Kiểm duyệt viên phòng ban của tài liệu và Admin sửa được vị trí.
"""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.borrowing.infrastructure.models import StorageLocation, documents_location
from app.modules.documents.application import queries as documents
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError, UnprocessableError

VIRTUAL_CODE = "KHO-CHUNG"
VIRTUAL_NAME = "Kho chung (không có bản cứng)"


def _require_admin(actor: Principal) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được quản lý kho lưu trữ")


def _snap(loc: StorageLocation) -> dict[str, Any]:
    return {"name": loc.name, "code": loc.code}


def general_location(db: Session) -> StorageLocation:
    """Kho chung (D-12); migration 0111 tạo sẵn, tạo lại nếu thiếu (CSDL dựng bằng metadata khi test)."""
    loc = db.scalar(select(StorageLocation).where(StorageLocation.is_virtual.is_(True)).limit(1))
    if loc is None:
        loc = StorageLocation(name=VIRTUAL_NAME, code=VIRTUAL_CODE, is_virtual=True)
        db.add(loc)
        db.flush()
    return loc


def list_locations(db: Session) -> list[StorageLocation]:
    general_location(db)
    return list(db.scalars(select(StorageLocation).order_by(StorageLocation.code)).all())


def get_location(db: Session, location_id: int) -> StorageLocation:
    loc = db.get(StorageLocation, location_id)
    if loc is None:
        raise NotFoundError("Không tìm thấy vị trí lưu trữ")
    return loc


def _check_code(db: Session, code: str, self_id: int | None = None) -> None:
    other = db.scalar(select(StorageLocation).where(StorageLocation.code == code))
    if other is not None and other.id != self_id:
        raise ConflictError("Mã vị trí đã tồn tại", code="LOCATION_DUPLICATE", fields={"code": "duplicate"})


def create_location(db: Session, actor: Principal, *, name: str, code: str, ctx: RequestContext) -> StorageLocation:
    _require_admin(actor)
    code = code.strip().upper()
    general_location(db)
    _check_code(db, code)
    loc = StorageLocation(name=name.strip(), code=code)
    db.add(loc)
    db.flush()
    record(
        db,
        action="create_storage_location",
        module="borrowing",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="storage_location",
        entity_id=loc.id,
        after=_snap(loc),
    )
    db.commit()
    return loc


def update_location(
    db: Session, actor: Principal, location_id: int, changes: dict[str, Any], ctx: RequestContext
) -> StorageLocation:
    _require_admin(actor)
    loc = get_location(db, location_id)
    if loc.is_virtual:
        raise ConflictError("Kho chung là vị trí hệ thống, không sửa được", code="LOCATION_SYSTEM")
    before = _snap(loc)
    if changes.get("name"):
        loc.name = str(changes["name"]).strip()
    if changes.get("code"):
        code = str(changes["code"]).strip().upper()
        _check_code(db, code, loc.id)
        loc.code = code
    record(
        db,
        action="update_storage_location",
        module="borrowing",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="storage_location",
        entity_id=loc.id,
        before=before,
        after=_snap(loc),
    )
    db.commit()
    return loc


def document_location_id(db: Session, document_id: uuid.UUID) -> int | None:
    return db.scalar(select(documents_location.c.storage_location_id).where(documents_location.c.id == document_id))


def physical_state(db: Session, document_id: uuid.UUID) -> tuple[bool | None, StorageLocation | None]:
    """(has_physical_copy, vị trí) của tài liệu."""
    row = db.execute(
        select(documents_location.c.has_physical_copy, documents_location.c.storage_location_id).where(
            documents_location.c.id == document_id
        )
    ).first()
    if row is None:
        return None, None
    return row[0], (db.get(StorageLocation, row[1]) if row[1] else None)


def get_document_location(db: Session, principal: Principal, document_id: uuid.UUID) -> StorageLocation | None:
    documents.ensure_can_view(db, principal, document_id)
    return physical_state(db, document_id)[1]


def _resolve(db: Session, has_physical_copy: bool | None, location_id: int | None) -> tuple[bool | None, int | None]:
    """Chuẩn hóa khai báo: có bản cứng → bắt buộc vị trí thật; không → Kho chung; None → suy ra từ vị trí."""
    if has_physical_copy is False:
        return False, general_location(db).id
    if location_id is None:
        if has_physical_copy:
            raise UnprocessableError(
                "Tài liệu có bản cứng phải chọn kho/kệ lưu trữ", fields={"storage_location_id": "required"}
            )
        return None, None
    loc = get_location(db, location_id)
    if loc.is_virtual:
        if has_physical_copy:
            raise UnprocessableError(
                "Tài liệu có bản cứng phải chọn kho/kệ thật, không phải Kho chung",
                fields={"storage_location_id": "virtual"},
            )
        return False, loc.id
    return True, loc.id


def _write(
    db: Session, principal: Principal, doc_id: uuid.UUID, has: bool | None, loc_id: int | None, ctx: RequestContext
) -> None:
    before_has, before_loc = physical_state(db, doc_id)
    db.execute(
        update(documents_location)
        .where(documents_location.c.id == doc_id)
        .values(storage_location_id=loc_id, has_physical_copy=has)
    )
    record(
        db,
        action="set_storage_location",
        module="borrowing",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc_id,
        document_id=doc_id,
        before={"storage_location_id": before_loc.id if before_loc else None, "has_physical_copy": before_has},
        after={"storage_location_id": loc_id, "has_physical_copy": has},
    )


def _ensure_can_set_location(db: Session, principal: Principal, document_id: uuid.UUID) -> Any:
    """D-11: gán vị trí là thao tác SỬA; D-12: sau khi xuất bản chủ sở hữu, KDV phòng ban của tài liệu, Admin."""
    try:
        return documents.ensure_can_edit(db, principal, document_id)
    except PermissionDeniedError:
        doc = documents.ensure_can_view(db, principal, document_id)
        if str(doc.approval_status) != "published":
            raise
        if documents.is_owner(principal, doc):
            return doc
        return documents.ensure_can_review(db, principal, document_id)


def set_document_location(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    location_id: int | None,
    ctx: RequestContext,
    *,
    has_physical_copy: bool | None = None,
) -> StorageLocation | None:
    doc = _ensure_can_set_location(db, principal, document_id)
    has, loc_id = _resolve(db, has_physical_copy, location_id)
    _write(db, principal, doc.id, has, loc_id, ctx)
    db.commit()
    return db.get(StorageLocation, loc_id) if loc_id else None


def declare_on_submit(
    db: Session, principal: Principal, document_id: uuid.UUID, payload: dict[str, Any], ctx: RequestContext
) -> None:
    """Hook "trước khi gửi duyệt" (D-12): khai báo bản cứng; thiếu và chưa từng khai báo → 422. Không commit."""
    has = payload.get("has_physical_copy")
    loc_id = payload.get("storage_location_id")
    if has is None and loc_id is None:
        declared, loc = physical_state(db, document_id)
        if declared is not None or loc is not None:
            return  # đã khai báo trước đó (sửa trên tab Mượn hồ sơ)
        raise UnprocessableError(
            "Gửi duyệt cần khai báo tài liệu có bản cứng hay không",
            code="PHYSICAL_COPY_REQUIRED",
            fields={"has_physical_copy": "required"},
        )
    resolved_has, resolved_loc = _resolve(db, has, loc_id)
    _write(db, principal, document_id, resolved_has, resolved_loc, ctx)
