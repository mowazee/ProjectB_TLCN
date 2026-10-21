"""ORM: categories (FR-02). is_active: ngừng sử dụng thay vì xóa."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.categories.domain.system import UNCLASSIFIED_CODE
from app.shared.db import Base, utcnow


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    retention_period_years: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    @property
    def is_system(self) -> bool:
        """D-10: "Chưa phân loại" - không chọn được khi tải lên/sửa, không được gợi ý."""
        return self.code == UNCLASSIFIED_CODE
