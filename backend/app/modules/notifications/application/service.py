"""Thông báo trong hệ thống (P2-07, dùng chung với P2-01).

DbNotifier hiện thực port Notifier của lõi: ghi notifications trong CÙNG transaction với thao tác
nghiệp vụ (duyệt, mượn/trả...), nên rollback thì không có thông báo "ma".
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.notifications.infrastructure.models import Notification
from app.shared.context import Principal
from app.shared.errors import NotFoundError
from app.shared.pagination import PageParams


class DbNotifier:
    def notify(
        self,
        db: Session,
        user_ids: list[uuid.UUID],
        *,
        title: str,
        message: str,
        type: str,
        link_url: str | None = None,
    ) -> None:
        for uid in dict.fromkeys(user_ids):  # bỏ trùng, giữ thứ tự
            db.add(
                Notification(user_id=uid, title=title[:255], message=message or None, type=type[:50], link_url=link_url)
            )
        db.flush()


def list_for_user(
    db: Session, principal: Principal, params: PageParams, *, unread_only: bool = False
) -> tuple[list[Notification], int, int]:
    """(items, total, unread) của người dùng hiện tại."""
    stmt = select(Notification).where(Notification.user_id == principal.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    unread = (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == principal.id, Notification.is_read.is_(False)
            )
        )
        or 0
    )
    items = db.scalars(
        stmt.order_by(Notification.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).all()
    return list(items), total, unread


def mark_read(db: Session, principal: Principal, notification_id: uuid.UUID) -> Notification:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != principal.id:  # không lộ thông báo của người khác
        raise NotFoundError("Không tìm thấy thông báo")
    n.is_read = True
    db.commit()
    return n


def mark_all_read(db: Session, principal: Principal) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == principal.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
