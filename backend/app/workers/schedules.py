"""Lịch Celery beat dựng từ ModuleSpec.schedules của module đang bật."""

from typing import Any


def beat_schedule() -> dict[str, Any]:
    from app import registry

    schedule: dict[str, Any] = {}
    for m in registry.enabled_modules():
        for name, s in m.schedules.items():
            schedule[f"{m.name}.{name}"] = {
                "task": "schedules.run",
                "schedule": s.every_seconds,
                "args": [name],
                "options": {"queue": "default"},
            }
    return schedule
