"""UC-09 Quản lý danh mục (FR-02) + API truy vấn công khai cho module khác.

D-10 (v0.9): danh mục hệ thống "Chưa phân loại" (UNCLASSIFIED_CODE) chứa tài liệu tải lên ở chế độ Danh mục gợi ý
trong lúc chờ tự phân loại. Không chọn được khi tải lên/sửa (CATEGORY_SYSTEM), không được gợi ý, không đổi mã hay ngừng
dùng được; tạo bởi migration 0109 (hoặc lần đầu cần tới).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.categories.domain.system import UNCLASSIFIED_CODE, UNCLASSIFIED_NAME
from app.modules.categories.infrastructure.models import Category
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError, UnprocessableError


@dataclass(frozen=True)
class CategoryInfo:
    id: int
    name: str
    code: str
    is_active: bool
    description: str | None

    @property
    def is_system(self) -> bool:
        return self.code == UNCLASSIFIED_CODE


def _info(c: Category) -> CategoryInfo:
    return CategoryInfo(c.id, c.name, c.code, c.is_active, c.description)


def is_system(c: Category) -> bool:
    return c.is_system


def unclassified_id(db: Session) -> int:
    """Id danh mục "Chưa phân loại" (tạo nếu CSDL chưa có, vd. cài mới không qua migration)."""
    cat = db.scalar(select(Category).where(Category.code == UNCLASSIFIED_CODE))
    if cat is None:
        cat = Category(
            name=UNCLASSIFIED_NAME,
            code=UNCLASSIFIED_CODE,
            description="Danh mục hệ thống: tài liệu chờ tự phân loại sau OCR (D-10)",
        )
        db.add(cat)
        db.flush()
    return cat.id


def _snapshot(c: Category) -> dict[str, Any]:
    return {
        "name": c.name,
        "code": c.code,
        "parent_id": c.parent_id,
        "retention_period_years": c.retention_period_years,
        "description": c.description,
        "is_active": c.is_active,
    }


def _require_admin(actor: Principal) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được quản lý danh mục")


# ---------------------------------------------------------------- truy vấn công khai
def list_categories(db: Session, *, active_only: bool = False) -> list[Category]:
    stmt = select(Category).order_by(Category.name)
    if active_only:
        stmt = stmt.where(Category.is_active.is_(True))
    return list(db.scalars(stmt).all())


def active_categories(db: Session) -> list[CategoryInfo]:
    return [_info(c) for c in list_categories(db, active_only=True)]


def require_active(db: Session, category_id: int) -> CategoryInfo:
    """Dùng khi upload/đổi danh mục: phải tồn tại, đang dùng và không phải danh mục hệ thống (422 nếu không)."""
    cat = db.get(Category, category_id)
    if cat is None:
        raise UnprocessableError(
            "Danh mục không tồn tại", code="CATEGORY_NOT_FOUND", fields={"category_id": "not_found"}
        )
    if is_system(cat):
        raise UnprocessableError(
            'Không chọn được danh mục hệ thống "Chưa phân loại"; hãy chọn danh mục cụ thể hoặc dùng Danh mục gợi ý',
            code="CATEGORY_SYSTEM",
            fields={"category_id": "system"},
        )
    if not cat.is_active:
        raise UnprocessableError(
            "Danh mục đã ngừng sử dụng", code="CATEGORY_INACTIVE", fields={"category_id": "inactive"}
        )
    return _info(cat)


def names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {i: n for i, n in db.execute(select(Category.id, Category.name).where(Category.id.in_(ids))).all()}


def snapshot(db: Session, category_id: int) -> dict[str, Any]:
    cat = db.get(Category, category_id)
    if cat is None:
        raise NotFoundError("Không tìm thấy danh mục")
    return _snapshot(cat)


# ---------------------------------------------------------------- ghi
def _check_parent(db: Session, parent_id: int | None, self_id: int | None = None) -> None:
    if parent_id is None:
        return
    if parent_id == self_id or db.get(Category, parent_id) is None:
        raise UnprocessableError("Danh mục cha không hợp lệ", fields={"parent_id": "invalid"})


def create_category(db: Session, actor: Principal | None, data: dict[str, Any], ctx: RequestContext) -> Category:
    if actor is not None:
        _require_admin(actor)
    code = str(data["code"]).strip().upper()
    if db.scalar(select(Category).where(Category.code == code)) is not None:
        raise ConflictError("Mã danh mục đã tồn tại", code="CATEGORY_DUPLICATE", fields={"code": "duplicate"})
    _check_parent(db, data.get("parent_id"))
    cat = Category(
        name=str(data["name"]).strip(),
        code=code,
        parent_id=data.get("parent_id"),
        retention_period_years=data.get("retention_period_years"),
        description=data.get("description"),
    )
    db.add(cat)
    db.flush()
    record(
        db,
        action="create_category",
        module="categories",
        actor_id=actor.id if actor else None,
        ctx=ctx,
        entity_type="category",
        entity_id=cat.id,
        after=_snapshot(cat),
    )
    db.commit()
    return cat


def update_category(
    db: Session,
    actor: Principal,
    category_id: int,
    changes: dict[str, Any],
    ctx: RequestContext,
    *,
    action: str | None = None,
) -> Category:
    _require_admin(actor)
    cat = db.get(Category, category_id)
    if cat is None:
        raise NotFoundError("Không tìm thấy danh mục")
    if is_system(cat) and (changes.get("is_active") is False or changes.get("parent_id") is not None):
        raise ConflictError("Không ngừng dùng hay đặt danh mục cha cho danh mục hệ thống", code="CATEGORY_SYSTEM")
    before = _snapshot(cat)
    if changes.get("name"):
        cat.name = str(changes["name"]).strip()
    if "parent_id" in changes:
        _check_parent(db, changes["parent_id"], cat.id)
        cat.parent_id = changes["parent_id"]
    for key in ("retention_period_years", "description"):
        if key in changes:
            setattr(cat, key, changes[key])
    if changes.get("is_active") is not None:
        cat.is_active = bool(changes["is_active"])
    after = _snapshot(cat)
    if action is None:
        action = "update_category"
        if before["is_active"] != after["is_active"]:
            action = "activate_category" if cat.is_active else "deactivate_category"
    record(
        db,
        action=action,
        module="categories",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="category",
        entity_id=cat.id,
        before=before,
        after=after,
    )
    db.commit()
    return cat
