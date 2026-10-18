"""FR-10 (UC-26): phòng ban - căn cứ phạm vi xem tài liệu (D-02). Ghi chỉ Admin; mọi thay đổi có audit.

Chỉ xóa được phòng ban không còn người dùng và tài liệu (409 DEPARTMENT_IN_USE): xóa phòng ban còn tài liệu sẽ
làm documents.department_id thành NULL (ON DELETE SET NULL) và tài liệu rơi khỏi phạm vi phòng ban.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application import queries as documents
from app.modules.users.application.manage import create_department, require_admin
from app.modules.users.infrastructure.models import Department, User
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, NotFoundError, UnprocessableError


@dataclass(frozen=True)
class DepartmentView:
    id: int
    code: str
    name: str
    description: str | None
    user_count: int
    document_count: int


def list_with_counts(db: Session) -> list[DepartmentView]:
    rows = db.execute(
        select(User.department_id, func.count(User.id))
        .where(User.department_id.isnot(None))
        .group_by(User.department_id)
    ).all()
    users = {int(dep): int(n) for dep, n in rows}
    docs = documents.count_by_department(db)
    return [
        DepartmentView(d.id, d.code, d.name, d.description, users.get(d.id, 0), docs.get(d.id, 0))
        for d in db.scalars(select(Department).order_by(Department.name)).all()
    ]


def _get(db: Session, department_id: int) -> Department:
    dep = db.get(Department, department_id)
    if dep is None:
        raise NotFoundError("Không tìm thấy phòng ban")
    return dep


def _snapshot(dep: Department) -> dict[str, str | None]:
    return {"code": dep.code, "name": dep.name, "description": dep.description}


def create(
    db: Session, actor: Principal, *, code: str, name: str, description: str | None, ctx: RequestContext
) -> Department:
    if not code.strip() or not name.strip():
        raise UnprocessableError("Mã và tên phòng ban không được để trống", fields={"code": "required"})
    dep = create_department(db, actor, code=code, name=name, ctx=ctx)
    if description and description.strip():
        dep.description = description.strip()
        db.commit()
    return dep


def update(
    db: Session, actor: Principal, department_id: int, changes: dict[str, str | None], ctx: RequestContext
) -> Department:
    require_admin(actor)
    dep = _get(db, department_id)
    before = _snapshot(dep)
    if changes.get("code") is not None:
        code = str(changes["code"]).strip().upper()
        if not code:
            raise UnprocessableError("Mã phòng ban không được để trống", fields={"code": "required"})
        if db.scalar(select(Department).where(Department.code == code, Department.id != dep.id)) is not None:
            raise ConflictError("Mã phòng ban đã tồn tại", code="DEPARTMENT_DUPLICATE", fields={"code": "duplicate"})
        dep.code = code
    if changes.get("name") is not None:
        name = str(changes["name"]).strip()
        if not name:
            raise UnprocessableError("Tên phòng ban không được để trống", fields={"name": "required"})
        dep.name = name
    if "description" in changes:
        dep.description = (changes["description"] or "").strip() or None
    record(
        db,
        action="update_department",
        module="users",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="department",
        entity_id=dep.id,
        before=before,
        after=_snapshot(dep),
    )
    db.commit()
    return dep


def delete(db: Session, actor: Principal, department_id: int, ctx: RequestContext) -> None:
    require_admin(actor)
    dep = _get(db, department_id)
    users = db.scalar(select(func.count(User.id)).where(User.department_id == dep.id)) or 0
    docs = documents.count_by_department(db).get(dep.id, 0)
    if users or docs:
        raise ConflictError(
            f"Phòng ban còn {users} người dùng và {docs} tài liệu, không xóa được",
            code="DEPARTMENT_IN_USE",
            details={"user_count": users, "document_count": docs},
        )
    before = _snapshot(dep)
    db.delete(dep)
    record(
        db,
        action="delete_department",
        module="users",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="department",
        entity_id=department_id,
        before=before,
    )
    db.commit()
