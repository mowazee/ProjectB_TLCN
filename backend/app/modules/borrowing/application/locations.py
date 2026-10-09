"""Kho lưu trữ hồ sơ bản cứng (P2-07): Admin quản lý; gán vị trí cho tài liệu."""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.borrowing.infrastructure.models import StorageLocation, documents_location
from app.modules.documents.application import queries as documents
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError


def _require_admin(actor: Principal) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được quản lý kho lưu trữ")


def _snap(loc: StorageLocation) -> dict[str, Any]:
    return {"name": loc.name, "code": loc.code}


def list_locations(db: Session) -> list[StorageLocation]:
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


def get_document_location(db: Session, principal: Principal, document_id: uuid.UUID) -> StorageLocation | None:
    documents.ensure_can_view(db, principal, document_id)
    loc_id = document_location_id(db, document_id)
    return db.get(StorageLocation, loc_id) if loc_id else None


def set_document_location(
    db: Session, principal: Principal, document_id: uuid.UUID, location_id: int | None, ctx: RequestContext
) -> StorageLocation | None:
    doc = documents.ensure_can_manage(db, principal, document_id)
    loc = get_location(db, location_id) if location_id is not None else None
    before = document_location_id(db, doc.id)
    db.execute(
        update(documents_location).where(documents_location.c.id == doc.id).values(storage_location_id=location_id)
    )
    record(
        db,
        action="set_storage_location",
        module="borrowing",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        before={"storage_location_id": before},
        after={"storage_location_id": location_id},
    )
    db.commit()
    return loc
