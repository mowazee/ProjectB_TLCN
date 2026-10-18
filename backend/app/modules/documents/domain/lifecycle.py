"""Trạng thái tài liệu (SDD mục 6): lifecycle tách riêng khỏi approval (P2-01)."""

from datetime import datetime, timedelta
from enum import StrEnum


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class ShareMode(StrEnum):
    """D-09 (SDD v0.8): chế độ chia sẻ, chỉ có hiệu lực khi tài liệu đã xuất bản."""

    PRIVATE = "private"  # chủ sở hữu, Admin, Kiểm duyệt viên phòng ban của tài liệu, người được thêm đích danh
    INTERNAL = "internal"  # mặc định: + phòng ban của tài liệu và các phòng ban được chọn
    PUBLIC = "public"  # mọi người dùng đã đăng nhập


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"


class PageOcrStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


def restore_deadline(deleted_at: datetime | None, retention_days: int) -> datetime | None:
    return deleted_at + timedelta(days=retention_days) if deleted_at else None


def can_restore_at(deleted_at: datetime | None, retention_days: int, now: datetime) -> bool:
    deadline = restore_deadline(deleted_at, retention_days)
    return deadline is not None and now <= deadline
