"""API users (SDD mục 7.1): GET/POST /api/users; PATCH /api/users/{id}; GET /api/roles.
Bổ sung GET /api/departments (danh sách phòng ban cho form người dùng)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_roles
from app.modules.users.application import manage
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


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: DbSession, _: CurrentPrincipal) -> list[DepartmentOut]:
    return [DepartmentOut.model_validate(d) for d in manage.list_departments(db)]
