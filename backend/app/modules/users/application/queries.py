"""API truy vấn công khai của module users (module khác chỉ dùng các hàm ở đây, R5)."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.users.infrastructure.models import Department, Role, User
from app.shared.context import Principal


@dataclass(frozen=True)
class Credentials:
    user_id: uuid.UUID
    password_hash: str
    is_active: bool


def to_principal(user: User) -> Principal:
    return Principal(user.id, user.username, user.full_name, user.department_id, user.role_codes)


def get_principal(db: Session, user_id: uuid.UUID) -> Principal | None:
    """Principal của user còn hoạt động; None nếu không tồn tại hoặc đã bị khóa."""
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return to_principal(user)


def find_credentials(db: Session, login: str) -> Credentials | None:
    """UC-00: đăng nhập bằng username hoặc email."""
    key = login.strip().lower()
    user = db.scalar(select(User).where(or_(User.username == key, User.email == key)))
    if user is None:
        return None
    return Credentials(user.id, user.password_hash, user.is_active)


def display_names(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    return {uid: name for uid, name in rows}


def user_ids_with_roles(db: Session, roles: set[str], department_id: int | None = None) -> list[uuid.UUID]:
    """Người nhận thông báo theo vai trò (Admin luôn được tính)."""
    stmt = select(User.id).join(User.roles).where(User.is_active.is_(True), Role.name.in_(roles | {"ADMIN"})).distinct()
    ids = list(db.scalars(stmt).all())
    if department_id is None:
        return ids
    same = set(db.scalars(select(User.id).where(User.id.in_(ids), User.department_id == department_id)).all())
    admins = set(db.scalars(select(User.id).join(User.roles).where(User.id.in_(ids), Role.name == "ADMIN")).all())
    return [i for i in ids if i in same or i in admins]


@dataclass(frozen=True)
class UserBrief:
    """Thông tin tối thiểu để hiển thị người được chia sẻ (FR-13) - không có email, vai trò."""

    id: uuid.UUID
    username: str
    full_name: str
    department_id: int | None
    department_name: str | None
    is_active: bool


def _brief_select() -> Select[Any]:
    return select(
        User.id, User.username, User.full_name, User.department_id, Department.name.label("dep_name"), User.is_active
    ).outerjoin(Department, Department.id == User.department_id)


def _briefs(db: Session, stmt: Select[Any]) -> list[UserBrief]:
    return [
        UserBrief(r.id, r.username, r.full_name, r.department_id, r.dep_name, r.is_active) for r in db.execute(stmt)
    ]


def user_briefs(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, UserBrief]:
    if not ids:
        return {}
    return {b.id: b for b in _briefs(db, _brief_select().where(User.id.in_(ids)))}


def lookup_users(db: Session, q: str, limit: int = 20) -> list[UserBrief]:
    """FR-13: tìm người dùng đang hoạt động theo họ tên/tên đăng nhập/email để chia sẻ."""
    term = f"%{q.strip().lower()}%"
    match = or_(
        func.lower(User.full_name).like(term), func.lower(User.username).like(term), func.lower(User.email).like(term)
    )
    stmt = _brief_select().where(User.is_active.is_(True), match).order_by(User.full_name).limit(limit)
    return _briefs(db, stmt)


def department_names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(db.execute(select(Department.id, Department.name).where(Department.id.in_(ids))).tuples().all())
