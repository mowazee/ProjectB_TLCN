"""Bảng notifications (ERD file 3 v0.6, P2-07/P2-01): id, user_id, title, message, type, link_url,
is_read, created_at.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base, utcnow


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(50))
    link_url: Mapped[str | None] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
