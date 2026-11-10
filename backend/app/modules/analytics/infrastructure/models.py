"""ORM: daily_activity_stats (FR-17, SDD v0.13) - bảng tổng hợp theo ngày, không xóa theo thời hạn audit (FR-14).

Phép chiếu chỉ đọc các bảng của module khác (audit_logs, documents, processing_jobs, users) - không import model
của module đó (R5), giống search/infrastructure/tables.py.
"""

import uuid
from datetime import date

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Uuid, column, table
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base, JSONType


class DailyActivityStat(Base):
    __tablename__ = "daily_activity_stats"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    metric: Mapped[str] = mapped_column(String(50), primary_key=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    value: Mapped[float] = mapped_column(Float, default=0)


audit_logs = table(
    "audit_logs",
    column("user_id", Uuid),
    column("document_id", Uuid),
    column("action", String),
    column("state_after", JSONType),
    column("created_at", DateTime(timezone=True)),
)
documents = table(
    "documents",
    column("id", Uuid),
    column("owner_id", Uuid),
    column("created_at", DateTime(timezone=True)),
)
processing_jobs = table(
    "processing_jobs",
    column("document_id", Uuid),
    column("kind", String),
    column("status", String),
    column("finished_at", DateTime(timezone=True)),
)
users = table("users", column("id", Uuid), column("department_id", Integer))
