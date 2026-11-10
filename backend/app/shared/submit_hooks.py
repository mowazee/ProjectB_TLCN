"""Điểm mở rộng "trước khi gửi duyệt" (D-12, SDD v0.13).

Module workflow (P2-01) gọi run() trong cùng transaction trước khi đổi approval_status sang pending_review;
module khác (borrowing, P2-07) đăng ký kiểm tra/ghi dữ liệu đi kèm (khai báo bản cứng). Không module nào
đăng ký thì gửi duyệt như trước. Hook ném lỗi AppError (vd. 422) để chặn gửi duyệt.
"""

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.shared.context import Principal, RequestContext

SubmitHook = Callable[[Session, Principal, uuid.UUID, dict[str, Any], RequestContext], None]

_hooks: list[SubmitHook] = []


def register(hook: SubmitHook) -> None:
    if hook not in _hooks:
        _hooks.append(hook)


def reset() -> None:
    _hooks.clear()


def run(
    db: Session, principal: Principal, document_id: uuid.UUID, payload: dict[str, Any], ctx: RequestContext
) -> None:
    for hook in _hooks:
        hook(db, principal, document_id, payload, ctx)
