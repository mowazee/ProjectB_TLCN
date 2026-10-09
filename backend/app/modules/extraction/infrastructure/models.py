"""Bảng document_extracted_fields (ERD file 3 v0.5, P2-04).

Cột theo ERD: id, document_id, field_name, field_value, extracted_method, is_verified.
UNIQUE(document_id, field_name) thêm ở migration P2-04 (chạy lại không tạo trường trùng).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class DocumentExtractedField(Base):
    __tablename__ = "document_extracted_fields"
    __table_args__ = (UniqueConstraint("document_id", "field_name", name="uq_extracted_fields_document_field"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    field_value: Mapped[str | None] = mapped_column(Text)
    extracted_method: Mapped[str] = mapped_column(String(30))  # regex-v1 | manual
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
