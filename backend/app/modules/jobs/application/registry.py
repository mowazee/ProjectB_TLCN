"""Job kind registry (điểm mở rộng): kind -> handler; OCR profile -> hàng đợi.

Module đăng ký qua ModuleSpec.job_handlers (registry.activate gọi register_handler).
P2-03 đăng ký profile "handwriting" -> queue "ocr_hw" và resolver chọn profile theo tài liệu.
"""

from collections.abc import Callable
from typing import Any

from app.modules.jobs.domain.model import OCR

_handlers: dict[str, Callable[[Any], None]] = {}
_ocr_queues: dict[str, str] = {"print": "ocr"}
# resolver(is_handwritten) -> profile hoặc None (để resolver khác/ mặc định quyết định)
_profile_resolvers: list[Callable[[bool], str | None]] = []

DEFAULT_QUEUES = {OCR: "ocr"}


def register_handler(kind: str, handler: Callable[[Any], None]) -> None:
    _handlers[kind] = handler


def get_handler(kind: str) -> Callable[[Any], None] | None:
    return _handlers.get(kind)


def register_ocr_profile(profile: str, queue: str, resolver: Callable[[bool], str | None] | None = None) -> None:
    _ocr_queues[profile] = queue
    if resolver is not None and resolver not in _profile_resolvers:
        _profile_resolvers.append(resolver)


def ocr_profiles() -> dict[str, str]:
    return dict(_ocr_queues)


def resolve_ocr_profile(is_handwritten: bool) -> str:
    for resolver in _profile_resolvers:
        profile = resolver(is_handwritten)
        if profile:
            return profile
    return "print"


def reset() -> None:
    _handlers.clear()
    _ocr_queues.clear()
    _ocr_queues["print"] = "ocr"
    _profile_resolvers.clear()
