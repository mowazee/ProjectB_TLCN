"""FR-14 (SDD v0.13): cấu hình hệ thống - thời gian lưu thùng rác và audit log (lõi, luôn bật)."""

from app.modules.settings.application.retention import purge_audit
from app.modules.settings.presentation.router import router
from app.shared.config import settings
from app.shared.modules import ModuleSpec, Schedule

MODULE = ModuleSpec(
    name="settings",
    router=router,
    permissions=["settings:manage"],
    schedules={"purge_audit": Schedule(purge_audit, settings.PURGE_INTERVAL_SECONDS)},
)
