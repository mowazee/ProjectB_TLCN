"""API users (SDD mục 7.1): GET/POST /api/users; PATCH /api/users/{id}; GET /api/roles.
GET /api/users/lookup (v0.8, FR-13): tra cứu người dùng để chia sẻ tài liệu (Nghiệp vụ, Admin).
Phòng ban (FR-10, v0.7): GET /api/departments (mọi người dùng, cho form/bộ lọc), POST/PATCH/DELETE (Admin).
POST /api/users/{id}/revoke-sessions (Admin, v0.7)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_roles
from app.modules.users.application import departments, manage, queries
from app.modules.users.domain.roles import ROLE_PERMISSIONS, ROLE_SUMMARIES, RoleCode
from app.modules.users.infrastructure.models import User
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(prefix="/api", tags=["users"])
AdminOnly = Depends(require_roles("ADMIN"))


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    description: str | None = None
    user_count: int = 0
    document_count: int = 0


class RoleOut(BaseModel):
    """FR-12: vai trò hệ thống cố định kèm ma trận quyền chỉ đọc (users/domain/roles.py)."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    summary: str = ""
    permissions: list[str] = []
    member_count: int = 0


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    department_id: int | None
    roles: list[str]
    last_login_at: datetime | None
    created_at: datetime


class UserIn(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,50}$")
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(min_length=1)
    department_id: int | None = None
    phone: str | None = Field(default=None, max_length=20)


class UserPatch(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    department_id: int | None = None
    roles: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        email=u.email,
        full_name=u.full_name,
        phone=u.phone,
        is_active=u.is_active,
        department_id=u.department_id,
        roles=sorted(u.role_codes),
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


@router.get("/users", response_model=Page[UserOut], dependencies=[AdminOnly])
def list_users(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: RoleCode | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
) -> Page[UserOut]:
    rows, total = manage.list_users(
        db, principal, params, q, role=role, department_id=department_id, is_active=is_active
    )
    return Page(items=[user_out(u) for u in rows], total=total, page=params.page, page_size=params.page_size)


class UserLookupOut(BaseModel):
    """FR-13: tối thiểu để chọn người chia sẻ - không có email, vai trò, trạng thái."""

    id: uuid.UUID
    username: str
    full_name: str
    department_name: str | None


@router.get("/users/lookup", response_model=list[UserLookupOut], dependencies=[Depends(require_roles("OFFICER"))])
def lookup_users(
    db: DbSession, q: Annotated[str, Query(min_length=2, max_length=100)], principal: CurrentPrincipal
) -> list[UserLookupOut]:
    """FR-13 (v0.8): tìm người dùng đang hoạt động để chia sẻ tài liệu (Nghiệp vụ, Admin); tối đa 20 kết quả."""
    return [
        UserLookupOut(id=u.id, username=u.username, full_name=u.full_name, department_name=u.department_name)
        for u in queries.lookup_users(db, q, limit=20)
        if u.id != principal.id
    ]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[AdminOnly])
def create_user(data: UserIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> UserOut:
    user = manage.create_user(db, principal, ctx=ctx, **data.model_dump(mode="json"))
    return user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut, dependencies=[AdminOnly])
def update_user(user_id: uuid.UUID, data: UserPatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> UserOut:
    user = manage.update_user(db, principal, user_id, data.model_dump(exclude_unset=True, mode="json"), ctx)
    return user_out(user)


@router.get("/roles", response_model=list[RoleOut], dependencies=[AdminOnly])
def list_roles(db: DbSession) -> list[RoleOut]:
    counts = manage.role_member_counts(db)
    out = []
    for r in manage.list_roles(db):
        code = RoleCode(r.name) if r.name in RoleCode.__members__ else None
        out.append(
            RoleOut(
                id=r.id,
                name=r.name,
                description=r.description,
                summary=ROLE_SUMMARIES.get(code, "") if code else "",
                permissions=ROLE_PERMISSIONS.get(code, []) if code else [],
                member_count=counts.get(r.id, 0),
            )
        )
    return out


@router.post("/users/{user_id}/revoke-sessions", dependencies=[AdminOnly])
def revoke_sessions(user_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> dict[str, int]:
    """FR-01 (v0.7): buộc đăng xuất mọi phiên của người dùng."""
    return {"revoked": manage.revoke_sessions(db, principal, user_id, ctx)}


class DepartmentIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)


class DepartmentPatch(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)


def _dep_out(db: DbSession, dep_id: int) -> DepartmentOut:
    return next(DepartmentOut.model_validate(d) for d in departments.list_with_counts(db) if d.id == dep_id)


@router.post(
    "/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED, dependencies=[AdminOnly]
)
def create_department(data: DepartmentIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> DepartmentOut:
    dep = departments.create(db, principal, code=data.code, name=data.name, description=data.description, ctx=ctx)
    return _dep_out(db, dep.id)


@router.patch("/departments/{department_id}", response_model=DepartmentOut, dependencies=[AdminOnly])
def update_department(
    department_id: int, data: DepartmentPatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> DepartmentOut:
    departments.update(db, principal, department_id, data.model_dump(exclude_unset=True), ctx)
    return _dep_out(db, department_id)


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminOnly])
def delete_department(department_id: int, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> None:
    departments.delete(db, principal, department_id, ctx)


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: DbSession, _: CurrentPrincipal) -> list[DepartmentOut]:
    return [DepartmentOut.model_validate(d) for d in departments.list_with_counts(db)]
