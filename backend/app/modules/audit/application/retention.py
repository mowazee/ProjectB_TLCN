"""Xóa audit log cũ hơn mốc thời gian (FR-14, SDD v0.13) - gọi bởi module settings."""

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.modules.audit.infrastructure.models import AuditLog


def delete_older_than(db: Session, cutoff: datetime) -> int:
    """Không commit; trả số dòng đã xóa."""
    result = db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    return int(getattr(result, "rowcount", 0) or 0)
