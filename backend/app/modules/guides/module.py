"""FR-21 (v0.16): Hướng dẫn sử dụng - Admin tải lên tài liệu hướng dẫn, mọi người dùng xem (lõi, luôn bật)."""

from app.modules.guides.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="guides", router=router, permissions=["guides:manage"])
