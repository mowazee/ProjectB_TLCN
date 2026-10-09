"""ORM: processing_jobs (ERD file 3 v0.5).

kind KHÔNG có CHECK cố định ở lõi ngoài 'OCR': migration của P2 mở rộng ràng buộc
(EXTRACT, CLASSIFY, BULK_IMPORT). document_id nullable: job cấp lô (BULK_IMPORT, P2-08)
chưa gắn tài liệu nào; mọi job khác luôn có document_id.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.jobs.domain.model import JobStatus
from app.shared.db import Base, JSONType, str_enum, utcnow


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint("attempt <= max_attempts", name="chk_job_attempt"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="chk_job_progress"),
        Index("idx_jobs_kind_status", "kind", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_pages.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    queue_name: Mapped[str] = mapped_column(String(50), default="default", server_default="default")
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "ck_jobs_status"), default=JobStatus.QUEUED, server_default=JobStatus.QUEUED.value
    )
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    worker_id: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_detail: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
