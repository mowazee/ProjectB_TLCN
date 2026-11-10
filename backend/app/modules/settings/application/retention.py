"""UC-30 Cấu hình thời gian lưu trữ (FR-14, SDD v0.13).

Giá trị lưu ở system_settings; chưa có dòng thì dùng mặc định từ cấu hình môi trường
(SOFT_DELETE_RETENTION_DAYS, AUDIT_RETENTION_DAYS). Celery beat xóa audit log quá hạn (purge_audit),
mỗi lượt ghi một dòng audit purge_audit sau khi xóa nên không xóa dòng do chính lượt đó tạo.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.audit.application.retention import delete_older_than
from app.modules.settings.domain.retention import AUDIT_KEY, TRASH_KEY, violations
from app.modules.settings.infrastructure.models import SystemSetting
from app.shared.config import settings
from app.shared.context import SYSTEM_CONTEXT, Principal, RequestContext
from app.shared.db import SessionLocal, utcnow
from app.shared.errors import PermissionDeniedError, UnprocessableError


def _defaults() -> dict[str, int]:
    return {TRASH_KEY: settings.SOFT_DELETE_RETENTION_DAYS, AUDIT_KEY: settings.AUDIT_RETENTION_DAYS}


def get_retention(db: Session) -> dict[str, int]:
    values = _defaults()
    for row in db.scalars(select(SystemSetting).where(SystemSetting.key.in_(list(values)))).all():
        values[row.key] = int(row.value)
    return values


def trash_retention_days(db: Session) -> int:
    """Số ngày giữ tài liệu trong thùng rác (FR-07, D-05) - dùng bởi documents."""
    return get_retention(db)[TRASH_KEY]


def update_retention(db: Session, actor: Principal, changes: dict[str, Any], ctx: RequestContext) -> dict[str, int]:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được cấu hình thời gian lưu trữ")
    values = {k: int(v) for k, v in changes.items() if v is not None and k in (TRASH_KEY, AUDIT_KEY)}
    errors = violations(values)
    if errors:
        raise UnprocessableError("; ".join(errors.values()), fields={k: "out_of_range" for k in errors})
    before = get_retention(db)
    for key, value in values.items():
        row = db.get(SystemSetting, key)
        if row is None:
            db.add(SystemSetting(key=key, value=value, updated_by=actor.id))
        else:
            row.value, row.updated_by = value, actor.id
    after = {**before, **values}
    record(
        db,
        action="update_settings",
        module="settings",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="system_settings",
        entity_id="retention",
        before=before,
        after=after,
    )
    db.commit()
    return after


def purge_audit() -> int:
    """Celery beat: xóa audit log vận hành cũ hơn thời hạn (FR-14).

    Lịch sử thay đổi của tài liệu giữ vĩnh viễn (D-15). Trả số dòng đã xóa.
    """
    with SessionLocal() as db:
        days = get_retention(db)[AUDIT_KEY]
        cutoff = utcnow() - timedelta(days=days)
        deleted = delete_older_than(db, cutoff)
        record(
            db,
            action="purge_audit",
            module="settings",
            actor_id=None,
            ctx=SYSTEM_CONTEXT,
            entity_type="audit_logs",
            entity_id=None,
            after={"deleted": deleted, "cutoff": cutoff.isoformat(), "retention_days": days},
        )
        db.commit()
        return deleted
