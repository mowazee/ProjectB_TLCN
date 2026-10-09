"""Domain event bus trong tiến trình (điểm mở rộng, Đặc tả đề tài v0.5 mục 4.3).

- Lõi định nghĩa và phát event; module P2/P3 chỉ subscribe (qua ModuleSpec.event_handlers).
- Event được gom theo Session và chỉ phát SAU KHI COMMIT; rollback thì bỏ.
- Handler chạy với session riêng; lỗi của handler được log, không làm hỏng request gốc.
- after_commit(db, fn): chạy hàm sau commit (dùng để gửi job sang hàng đợi, NFR-03).
"""

import logging
from collections.abc import Callable

from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

from app.shared.domain_events import Event, EventBus, EventHandler, bus

__all__ = ["Event", "EventBus", "EventHandler", "after_commit", "bus", "publish"]

logger = logging.getLogger(__name__)

_PENDING = "pending_after_commit"


def after_commit(db: Session, fn: Callable[[], None]) -> None:
    db.info.setdefault(_PENDING, []).append(fn)


def publish(db: Session, evt: Event) -> None:
    """Phát event sau khi transaction hiện tại commit thành công."""
    after_commit(db, lambda: bus.dispatch(evt))


@sa_event.listens_for(Session, "after_commit")
def _run_after_commit(session: Session) -> None:
    # SQLAlchemy cũng phát after_commit khi RELEASE SAVEPOINT; chỉ chạy khi transaction gốc commit.
    if session.in_nested_transaction():
        return
    pending = session.info.pop(_PENDING, [])
    for fn in pending:
        try:
            fn()
        except Exception:
            logger.exception("Tác vụ sau commit lỗi")


@sa_event.listens_for(Session, "after_rollback")
def _drop_after_rollback(session: Session) -> None:
    if session.in_nested_transaction():  # rollback savepoint (vd. ghi audit lỗi) không hủy việc của transaction gốc
        return
    session.info.pop(_PENDING, None)
