"""Use case quản lý người dùng, vai trò, phòng ban (FR-01, UC-06)."""

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.users.domain.roles import DEFAULT_DEPARTMENT, ROLE_DESCRIPTIONS, RoleCode
from app.modules.users.infrastructure.models import Department, Role, User, UserRole
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError, UnprocessableError
from app.shared.pagination import PageParams
from app.shared.security.passwords import hash_password
from app.shared.security.session import get_session_store


def require_admin(actor: Principal) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được thực hiện thao tác này")


def seed_reference_data(db: Session) -> None:
    """Vai trò + phòng ban mặc định. Chạy lại an toàn."""
    existing = set(db.scalars(select(Role.name)).all())
    for code, desc in ROLE_DESCRIPTIONS.items():
        if code.value not in existing:
            db.add(Role(name=code.value, description=desc))
    dep_code, dep_name = DEFAULT_DEPARTMENT
    if db.scalar(select(Department).where(Department.code == dep_code)) is None:
        db.add(Department(code=dep_code, name=dep_name, description="Đơn vị mặc định"))
    db.commit()


def _snapshot(u: User) -> dict[str, Any]:
    return {
        "username": u.username,
        "email": u.email,
        "full_name": u.full_name,
        "phone": u.phone,
        "department_id": u.department_id,
        "roles": sorted(u.role_codes),
        "is_active": u.is_active,
    }


def _roles(db: Session, codes: list[str]) -> list[Role]:
    try:
        wanted = {RoleCode(c).value for c in codes}
    except ValueError as exc:
        raise UnprocessableError("Vai trò không hợp lệ", fields={"roles": "invalid"}) from exc
    roles = list(db.scalars(select(Role).where(Role.name.in_(wanted))).all())
    if not wanted or len(roles) != len(wanted):
        raise UnprocessableError("Vai trò không hợp lệ", fields={"roles": "invalid"})
    return roles


def _check_department(db: Session, department_id: int | None) -> None:
    if department_id is not None and db.get(Department, department_id) is None:
        raise UnprocessableError("Phòng ban không tồn tại", fields={"department_id": "not_found"})


def get_user(db: Session, actor: Principal, user_id: uuid.UUID) -> User:
    require_admin(actor)
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Không tìm thấy người dùng")
    return user


def list_users(
    db: Session,
    actor: Principal,
    params: PageParams,
    q: str | None = None,
    *,
    role: str | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
) -> tuple[list[User], int]:
    """FR-01 (v0.7): lọc theo từ khóa, vai trò, phòng ban, trạng thái."""
    require_admin(actor)
    stmt = select(User)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.username).like(like),
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
            )
        )
    if role:
        stmt = stmt.where(User.roles.any(Role.name == role))
    if department_id is not None:
        stmt = stmt.where(User.department_id == department_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.created_at).offset(params.offset).limit(params.page_size)).all()
    return list(rows), total


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.id)).all())


def role_member_counts(db: Session) -> dict[int, int]:
    """FR-12: số người dùng (kể cả đang khóa) của từng vai trò."""
    rows = db.execute(
        select(Role.id, func.count(UserRole.user_id)).outerjoin(UserRole, UserRole.role_id == Role.id).group_by(Role.id)
    ).all()
    return {role_id: int(n) for role_id, n in rows}


def list_departments(db: Session) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.name)).all())


def create_department(db: Session, actor: Principal | None, *, code: str, name: str, ctx: RequestContext) -> Department:
    if actor is not None:
        require_admin(actor)
    code = code.strip().upper()
    if db.scalar(select(Department).where(Department.code == code)) is not None:
        raise ConflictError("Mã phòng ban đã tồn tại", code="DEPARTMENT_DUPLICATE")
    dep = Department(code=code, name=name.strip())
    db.add(dep)
    db.flush()
    record(
        db,
        action="create_department",
        module="users",
        actor_id=actor.id if actor else None,
        ctx=ctx,
        entity_type="department",
        entity_id=dep.id,
        after={"code": code, "name": dep.name},
    )
    db.commit()
    return dep


def create_user(
    db: Session,
    actor: Principal | None,
    *,
    username: str,
    email: str,
    full_name: str,
    password: str,
    roles: list[str],
    department_id: int | None = None,
    phone: str | None = None,
    ctx: RequestContext,
) -> User:
    """actor=None chỉ dùng cho CLI/seed tạo Admin đầu tiên."""
    if actor is not None:
        require_admin(actor)
    username, email = username.strip().lower(), email.strip().lower()
    dup = db.scalar(select(User).where(or_(User.username == username, User.email == email)))
    if dup is not None:
        field = "username" if dup.username == username else "email"
        raise ConflictError("Tên đăng nhập hoặc email đã tồn tại", code="USER_DUPLICATE", fields={field: "duplicate"})
    _check_department(db, department_id)
    user = User(
        username=username,
        email=email,
        full_name=full_name.strip(),
        phone=phone,
        password_hash=hash_password(password),
        department_id=department_id,
        roles=_roles(db, roles),
    )
    db.add(user)
    db.flush()
    record(
        db,
        action="create_user",
        module="users",
        actor_id=actor.id if actor else None,
        ctx=ctx,
        entity_type="user",
        entity_id=user.id,
        after=_snapshot(user),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Tên đăng nhập hoặc email đã tồn tại", code="USER_DUPLICATE") from exc
    return user


def update_user(
    db: Session, actor: Principal, user_id: uuid.UUID, changes: dict[str, Any], ctx: RequestContext
) -> User:
    """changes chỉ chứa trường người dùng gửi lên (PATCH). Khóa tài khoản thu hồi mọi session."""
    user = get_user(db, actor, user_id)
    before = _snapshot(user)
    if user.id == actor.id:
        if changes.get("is_active") is False:
            raise UnprocessableError("Không thể tự khóa tài khoản của chính mình")
        if "roles" in changes and "ADMIN" not in (changes["roles"] or []):
            raise UnprocessableError("Không thể tự gỡ vai trò Quản trị viên của chính mình")
    if "email" in changes and changes["email"]:
        email = str(changes["email"]).strip().lower()
        if db.scalar(select(User).where(User.email == email, User.id != user.id)) is not None:
            raise ConflictError("Email đã tồn tại", code="USER_DUPLICATE", fields={"email": "duplicate"})
        user.email = email
    if changes.get("full_name"):
        user.full_name = str(changes["full_name"]).strip()
    if "phone" in changes:
        user.phone = changes["phone"]
    if "department_id" in changes:
        _check_department(db, changes["department_id"])
        user.department_id = changes["department_id"]
    if changes.get("roles") is not None:
        user.roles = _roles(db, changes["roles"])
    if changes.get("is_active") is not None:
        user.is_active = bool(changes["is_active"])
    if changes.get("password"):
        user.password_hash = hash_password(changes["password"])
    after = _snapshot(user)
    action = "update_user"
    if before["is_active"] != after["is_active"]:
        action = "unlock_user" if user.is_active else "lock_user"
    record(
        db,
        action=action,
        module="users",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={**after, "password_reset": bool(changes.get("password"))},
    )
    db.commit()
    if not user.is_active:
        get_session_store().revoke_user(user.id)  # SDD mục 3: phiên hiện có bị thu hồi
    return user


def find_first_admin(db: Session) -> User | None:
    return db.scalar(
        select(User)
        .join(User.roles)
        .where(Role.name == "ADMIN", User.is_active.is_(True))
        .order_by(User.created_at)
        .limit(1)
    )


def mark_login(db: Session, user_id: uuid.UUID) -> None:
    from app.shared.db import utcnow

    user = db.get(User, user_id)
    if user is not None:
        user.last_login_at = utcnow()
