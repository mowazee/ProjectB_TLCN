"""Tra cứu audit log (UC-08, chỉ Admin). get_log dùng cho rollback (P2-09)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.infrastructure.models import AuditLog
from app.shared.config import settings
from app.shared.context import Principal
from app.shared.errors import NotFoundError, PermissionDeniedError
from app.shared.pagination import PageParams


@dataclass
class AuditFilter:
    date_from: date | None = None
    date_to: date | None = None
    user_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    action: str | None = None


def _day_start_utc(day: date) -> datetime:
    """00:00 giờ địa phương quy đổi sang UTC để so với created_at."""
    return datetime.combine(day, time.min, tzinfo=settings.tz).astimezone(UTC)


def list_logs(db: Session, actor: Principal, flt: AuditFilter, params: PageParams) -> tuple[list[AuditLog], int]:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được xem nhật ký hệ thống")
    stmt = select(AuditLog)
    if flt.date_from:
        stmt = stmt.where(AuditLog.created_at >= _day_start_utc(flt.date_from))
    if flt.date_to:
        stmt = stmt.where(AuditLog.created_at < _day_start_utc(flt.date_to + timedelta(days=1)))
    if flt.user_id:
        stmt = stmt.where(AuditLog.user_id == flt.user_id)
    if flt.document_id:
        stmt = stmt.where(AuditLog.document_id == flt.document_id)
    if flt.action:
        stmt = stmt.where(AuditLog.action == flt.action.strip().lower())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(params.offset).limit(params.page_size)
    ).all()
    return list(rows), total


def get_log(db: Session, log_id: int) -> AuditLog:
    log = db.get(AuditLog, log_id)
    if log is None:
        raise NotFoundError("Không tìm thấy dòng nhật ký")
    return log


def latest_log_for_entity(db: Session, entity_type: str, entity_id: str) -> AuditLog | None:
    return db.scalar(
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id, AuditLog.result == "success")
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
