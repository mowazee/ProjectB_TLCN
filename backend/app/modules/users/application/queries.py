"""API truy vấn công khai của module users (module khác chỉ dùng các hàm ở đây, R5)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.users.infrastructure.models import Role, User
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
