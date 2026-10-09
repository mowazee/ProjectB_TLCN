"""P2-07 mượn hồ sơ: cờ "borrowing" (thông báo cần thêm cờ "notifications")."""

from app.modules.borrowing.application import requests
from app.modules.borrowing.presentation.router import router
from app.modules.dashboard.application.stats import register_contributor
from app.shared.config import settings
from app.shared.modules import ModuleSpec, Schedule


def _setup() -> None:
    register_contributor(requests.dashboard_counts)


MODULE = ModuleSpec(
    name="borrowing",
    feature="borrowing",
    router=router,
    permissions=["borrow:request", "borrow:decide", "storage:manage"],
    schedules={"remind_overdue_borrows": Schedule(requests.remind_overdue, settings.BORROW_REMIND_INTERVAL_SECONDS)},
    setup=_setup,
)
