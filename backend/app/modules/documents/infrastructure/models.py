"""ORM: documents, document_pages (ERD file 3 v0.5, SDD mục 6).

Ba cột trạng thái tách riêng: lifecycle_status (ở đây), processing_jobs.status (module jobs),
approval_status (P2-01, cột có sẵn từ MVP). documents.storage_location_id do module
borrowing (P2-07) thêm bằng migration riêng.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.documents.domain.lifecycle import ApprovalStatus, LifecycleStatus, PageOcrStatus
from app.shared.db import Base, str_enum, utcnow

FILE_TYPES = {"application/pdf": "PDF", "image/png": "PNG", "image/jpeg": "JPG"}


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    document_code: Mapped[str | None] = mapped_column(String(100))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))  # không bao giờ trả ra client
    mime_type: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int] = mapped_column(BigInteger)
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        str_enum(LifecycleStatus, "ck_documents_lifecycle_status"),
        default=LifecycleStatus.ACTIVE,
        server_default=LifecycleStatus.ACTIVE.value,
        index=True,
    )
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        str_enum(ApprovalStatus, "ck_documents_approval_status"),
        default=ApprovalStatus.DRAFT,
        server_default=ApprovalStatus.DRAFT.value,
    )
    is_handwritten: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def file_type(self) -> str:
        return FILE_TYPES.get(self.mime_type, self.mime_type)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number", name="uq_document_page"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_key: Mapped[str] = mapped_column(String(500))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    ocr_status: Mapped[PageOcrStatus] = mapped_column(
        str_enum(PageOcrStatus, "ck_document_pages_ocr_status"),
        default=PageOcrStatus.PENDING,
        server_default=PageOcrStatus.PENDING.value,
    )
