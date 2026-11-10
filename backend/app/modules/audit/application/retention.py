"""Xóa audit log vận hành cũ hơn mốc thời gian (FR-14, D-15 SDD v0.14) - gọi bởi module settings.

D-15: lịch sử thay đổi của tài liệu còn tồn tại (dòng có document_id, trừ nhóm đọc) giữ vĩnh viễn.
Chỉ xóa log vận hành:
- dòng không gắn tài liệu (document_id NULL: đăng nhập, quản trị, log của tài liệu đã xóa cứng vì FK SET NULL);
- dòng thuộc nhóm đọc (xem, tải, xác thực/xem/tải qua link ngoài).
"""

import uuid
from datetime import datetime

from sqlalchemy import String, column, delete, func, or_, select, table
from sqlalchemy.orm import Session

from app.modules.audit.infrastructure.models import AuditLog

documents = table("documents", column("id"))  # chỉ đọc id, không phụ thuộc module documents

READ_ACTIONS = frozenset(
    {
        "download_document",
        "download_attachment",
        "download_bundle",
        "external_verify",
        "external_view",
        "external_download",
    }
)


def delete_older_than(db: Session, cutoff: datetime) -> int:
    """Không commit; trả số dòng log vận hành đã xóa."""
    stmt = delete(AuditLog).where(
        AuditLog.created_at < cutoff,
        or_(AuditLog.document_id.is_(None), AuditLog.action.in_(READ_ACTIONS)),
    )
    result = db.execute(stmt.execution_options(synchronize_session=False))
    return int(getattr(result, "rowcount", 0) or 0)


def delete_orphaned_document_logs(db: Session) -> int:
    """Xóa nhật ký còn sót của tài liệu đã bị xóa vĩnh viễn trước v0.15 (khi đó purge giữ log, document_id = NULL):
    dòng có entity_type = 'document' mà tài liệu không còn tồn tại. Không commit."""

    def norm(x):  # type: ignore[no-untyped-def]
        # SQLite lưu UUID dạng 32 ký tự hex, PostgreSQL dạng có gạch: so sánh sau khi bỏ "-" và hạ chữ thường
        return func.replace(func.lower(func.cast(x, String)), "-", "")

    still_exists = (
        select(documents.c.id).where(norm(documents.c.id) == norm(AuditLog.entity_id)).correlate(AuditLog).exists()
    )
    result = db.execute(
        delete(AuditLog)
        .where(
            AuditLog.document_id.is_(None),
            AuditLog.entity_type == "document",
            AuditLog.entity_id.is_not(None),
            ~still_exists,
        )
        .execution_options(synchronize_session=False)
    )
    return int(getattr(result, "rowcount", 0) or 0)


def delete_for_document(db: Session, document_id: uuid.UUID) -> int:
    """Xóa toàn bộ nhật ký của một tài liệu khi tài liệu bị xóa vĩnh viễn (quá hạn thùng rác). Không commit."""
    result = db.execute(
        delete(AuditLog).where(AuditLog.document_id == document_id).execution_options(synchronize_session=False)
    )
    return int(getattr(result, "rowcount", 0) or 0)
