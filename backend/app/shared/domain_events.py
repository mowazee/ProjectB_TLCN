"""Lớp gốc domain event và bus trong tiến trình (thuần Python để lớp domain import được, R3).

Phát event sau commit: app.shared.events.publish().
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("app.shared.events")


@dataclass(frozen=True)
class Event:
    """Lớp gốc của domain event."""


EventHandler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def clear(self) -> None:
        self._handlers.clear()

    def dispatch(self, evt: Event) -> None:
        for handler in list(self._handlers.get(type(evt), [])):
            try:
                handler(evt)
            except Exception:
                logger.exception("Event handler %s lỗi với %s", handler, type(evt).__name__)


bus = EventBus()
