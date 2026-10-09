"""ModuleSpec: hợp đồng nội bộ giữa lõi và module (chốt ở M0, Đặc tả đề tài v0.5 mục 4.6).

Mỗi module khai báo MODULE = ModuleSpec(...) trong module.py. registry.enabled_modules()
nạp module lõi (feature=None) và module P2/P3 có cờ bật trong FEATURES_ENABLED.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

from app.shared.domain_events import Event

JobHandler = Callable[[Any], None]  # nhận jobs.application.JobContext
EventHandler = Callable[[Any], None]


@dataclass(frozen=True)
class Schedule:
    """Tác vụ định kỳ cho Celery beat: gọi fn() mỗi every_seconds giây."""

    fn: Callable[[], Any]
    every_seconds: float


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    feature: str | None = None  # None = lõi MVP, luôn bật
    router: APIRouter | None = None
    routers: tuple[APIRouter, ...] = ()
    job_handlers: dict[str, JobHandler] = field(default_factory=dict)
    event_handlers: list[tuple[type[Event], EventHandler]] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    schedules: dict[str, Schedule] = field(default_factory=dict)
    # Đăng ký vào registry của lõi (engine OCR, contributor dashboard, notifier...)
    setup: Callable[[], None] | None = None

    def all_routers(self) -> tuple[APIRouter, ...]:
        return ((self.router,) if self.router else ()) + self.routers
