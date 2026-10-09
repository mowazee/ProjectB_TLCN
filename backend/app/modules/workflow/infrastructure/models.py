"""Bảng document_approvals (ERD file 3 v0.5, P2-01): lịch sử append-only.

Cột theo ERD: id, document_id, approver_id (người thực hiện action), action, comments.
created_at thêm để hiển thị lịch sử theo thời gian (ghi nhận chênh lệch trong SUMMARY.md).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base, utcnow


class DocumentApproval(Base):
    __tablename__ = "document_approvals"
    __table_args__ = (
        CheckConstraint(
            "action IN ('submit', 'approve', 'reject', 'publish', 'unpublish')", name="ck_document_approvals_action"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(20))
    comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
