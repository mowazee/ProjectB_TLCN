"""Notifier port (Đặc tả đề tài v0.5 mục 4.3).

Module notifications (P2-07) đăng ký hiện thực khi cờ bật; mặc định là NullNotifier nên
module khác (workflow, borrowing) gọi notify() an toàn dù notifications đang tắt.
"""

import uuid
from typing import Protocol

from sqlalchemy.orm import Session


class Notifier(Protocol):
    def notify(
        self,
        db: Session,
        user_ids: list[uuid.UUID],
        *,
        title: str,
        message: str,
        type: str,
        link_url: str | None = None,
    ) -> None: ...


class NullNotifier:
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
        return None


_notifier: Notifier = NullNotifier()


def set_notifier(notifier: Notifier) -> None:
    global _notifier
    _notifier = notifier


def reset_notifier() -> None:
    set_notifier(NullNotifier())


def get_notifier() -> Notifier:
    return _notifier
