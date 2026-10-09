"""Bảng P2-07 (ERD file 3 v0.5): storage_locations, borrow_requests và cột documents.storage_location_id.

- storage_locations: id, name, code.
- borrow_requests: id, document_id, requester_id, approver_id, status, from_date, to_date
  (+ purpose, created_at: UC-11 yêu cầu nhập mục đích và cần sắp xếp theo thời gian tạo; ghi nhận
  chênh lệch với ERD trong SUMMARY.md). "Quá hạn" được tính từ to_date, không lưu cột.
- documents.storage_location_id "chỉ thêm khi P2-07 triển khai" (SDD mục 6): module này gắn cột
  vào bảng documents của lõi (không sửa model lõi) và migration P2-07 tạo cột trong CSDL.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    column,
    func,
    table,
)
from sqlalchemy.orm import Mapped, mapped_column

# Ngoại lệ R5 có chủ đích (khai báo ignore_imports trong pyproject): bảng documents phải nạp trước khi
# gắn cột storage_location_id. Chỉ dùng metadata, không dùng class Document.
import app.modules.documents.infrastructure.models  # noqa: F401
from app.shared.db import Base, utcnow


class StorageLocation(Base):
    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    code: Mapped[str] = mapped_column(String(50), unique=True)


class BorrowRequest(Base):
    __tablename__ = "borrow_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'returned')", name="ck_borrow_requests_status"),
        CheckConstraint("from_date <= to_date", name="ck_borrow_requests_dates"),
        Index("ix_borrow_requests_document_status", "document_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    requester_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    purpose: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())


def _attach_document_column() -> None:
    documents = Base.metadata.tables["documents"]
    if "storage_location_id" not in documents.c:
        documents.append_column(
            Column(
                "storage_location_id",
                Integer,
                ForeignKey("storage_locations.id", ondelete="SET NULL", name="fk_documents_storage_location_id"),
                nullable=True,
                index=True,
            )
        )


_attach_document_column()

# Projection để đọc/ghi cột vừa gắn mà không import model của module documents (R5)
documents_location = table("documents", column("id", Uuid), column("storage_location_id", Integer))
