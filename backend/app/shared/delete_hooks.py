"""Điểm mở rộng "trước khi xóa tài liệu" (v0.17).

Module documents gọi run() trong cùng transaction trước khi chuyển tài liệu vào thùng rác; module khác (borrowing,
P2-07) đăng ký kiểm tra dữ liệu đi kèm: hồ sơ bản cứng đang được mượn, yêu cầu mượn đang chờ. Hook ném AppError
(vd. 409 kèm thông báo cần xác nhận) để chặn xóa, hoặc cập nhật dữ liệu của mình khi người xóa đã xác nhận
(options["confirm_borrows"]). Không module nào đăng ký thì xóa như trước.
"""

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.shared.context import Principal, RequestContext

DeleteHook = Callable[[Session, Principal, uuid.UUID, dict[str, Any], RequestContext], None]

_hooks: list[DeleteHook] = []


def register(hook: DeleteHook) -> None:
    if hook not in _hooks:
        _hooks.append(hook)


def reset() -> None:
    _hooks.clear()


def run(
    db: Session, principal: Principal, document_id: uuid.UUID, options: dict[str, Any], ctx: RequestContext
) -> None:
    for hook in _hooks:
        hook(db, principal, document_id, options, ctx)
