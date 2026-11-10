"""Xóa audit log vận hành cũ hơn mốc thời gian (FR-14, D-15 SDD v0.14) - gọi bởi module settings.

D-15: lịch sử thay đổi của tài liệu còn tồn tại (dòng có document_id, trừ nhóm đọc) giữ vĩnh viễn.
Chỉ xóa log vận hành:
- dòng không gắn tài liệu (document_id NULL: đăng nhập, quản trị, log của tài liệu đã xóa cứng vì FK SET NULL);
- dòng thuộc nhóm đọc (xem, tải, xác thực/xem/tải qua link ngoài).
"""

from datetime import datetime

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.modules.audit.infrastructure.models import AuditLog

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
