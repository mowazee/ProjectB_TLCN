"""CSRF token gắn với session và kiểm Origin (SDD mục 14, NFR-02)."""

import secrets
from urllib.parse import urlsplit

from app.shared.config import settings

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER = "x-csrf-token"


def tokens_match(expected: str | None, given: str | None) -> bool:
    return bool(expected and given) and secrets.compare_digest(str(expected), str(given))


def origin_allowed(origin: str | None, referer: str | None, host: str | None) -> bool:
    """Origin (hoặc Referer khi thiếu Origin) phải là cùng origin hoặc nằm trong allowlist.
    Không có cả hai header (client không phải trình duyệt, ví dụ test/CLI) thì cho qua:
    CSRF chỉ khai thác được qua trình duyệt, vốn luôn gửi Origin cho request ghi."""
    source = origin or referer
    if not source:
        return True
    parts = urlsplit(source)
    value = f"{parts.scheme}://{parts.netloc}".rstrip("/")
    if value in settings.allowed_origins:
        return True
    return bool(host) and parts.netloc == host
