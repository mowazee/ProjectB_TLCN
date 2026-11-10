"""FR-17 (SDD v0.13): thống kê hoạt động theo người dùng và phòng ban (lõi, chỉ Admin)."""

from app.modules.analytics.application.stats import refresh_recent
from app.modules.analytics.presentation.router import router
from app.shared.modules import ModuleSpec, Schedule

MODULE = ModuleSpec(
    name="analytics",
    router=router,
    permissions=["analytics:read"],
    schedules={"refresh_activity_stats": Schedule(refresh_recent, 3600)},
)
