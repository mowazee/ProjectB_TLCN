"""ORM: ocr_results, ocr_corrections (ERD file 3 v0.5).

- ocr_results: một kết quả theo (page_id, job_id) nên retry không tạo bản ghi trùng.
  search_vector do module search quản lý (chỉ mục trên text hiệu lực).
- ocr_corrections: version tăng dần, UNIQUE(page_id, version); version hiện hành = max(version).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.ocr.domain.ports import TEXT_LAYER_ENGINE
from app.shared.db import Base, JSONType, SearchVectorType, utcnow


class OcrResult(Base):
    __tablename__ = "ocr_results"
    __table_args__ = (
        UniqueConstraint("page_id", "job_id", name="uq_ocr_results_page_job"),
        Index("idx_ocr_results_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_pages.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processing_jobs.id", ondelete="SET NULL"))
    raw_text: Mapped[str] = mapped_column(Text)
    boxes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    engine_version: Mapped[str] = mapped_column(String(50))
    search_vector: Mapped[Any] = mapped_column(SearchVectorType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    @property
    def is_text_layer(self) -> bool:
        return self.engine_version.startswith(TEXT_LAYER_ENGINE)


class OcrCorrection(Base):
    __tablename__ = "ocr_corrections"
    __table_args__ = (UniqueConstraint("page_id", "version", name="uq_ocr_corrections_page_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_pages.id", ondelete="CASCADE"), index=True)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer)
    corrected_text: Mapped[str] = mapped_column(Text)
    base_version: Mapped[int] = mapped_column(Integer)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
