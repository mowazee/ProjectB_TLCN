"""P2-09 rollback thay đổi: cờ "rollback"; gọi use case của lõi, không ghi bảng lõi trực tiếp."""

from app.modules.rollback.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="rollback", feature="rollback", router=router, permissions=["audit:rollback"])
