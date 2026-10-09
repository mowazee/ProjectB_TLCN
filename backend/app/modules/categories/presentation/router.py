"""API categories (SDD mục 7.1): GET (đã đăng nhập), POST/PATCH (Admin). Ngừng dùng thay vì xóa."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_roles
from app.modules.categories.application import manage

router = APIRouter(prefix="/api/categories", tags=["categories"])


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    parent_id: int | None
    retention_period_years: int | None
    description: str | None
    is_active: bool
    created_at: datetime


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    parent_id: int | None = None
    retention_period_years: int | None = Field(default=None, ge=0, le=200)
    description: str | None = None


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    parent_id: int | None = None
    retention_period_years: int | None = Field(default=None, ge=0, le=200)
    description: str | None = None
    is_active: bool | None = None


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, _: CurrentPrincipal, active_only: bool = False) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in manage.list_categories(db, active_only=active_only)]


@router.post(
    "", response_model=CategoryOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("ADMIN"))]
)
def create_category(data: CategoryIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> CategoryOut:
    return CategoryOut.model_validate(manage.create_category(db, principal, data.model_dump(), ctx))


@router.patch("/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_roles("ADMIN"))])
def update_category(
    category_id: int, data: CategoryPatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> CategoryOut:
    cat = manage.update_category(db, principal, category_id, data.model_dump(exclude_unset=True), ctx)
    return CategoryOut.model_validate(cat)
