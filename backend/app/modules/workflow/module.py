"""P2-01 duyệt/xuất bản: cờ "workflow". Thông báo qua Notifier (bật thêm cờ notifications)."""

from app.modules.dashboard.application.stats import register_contributor
from app.modules.workflow.application.approvals import pending_count
from app.modules.workflow.presentation.router import router
from app.shared.modules import ModuleSpec


def _setup() -> None:
    register_contributor(pending_count)


MODULE = ModuleSpec(
    name="workflow",
    feature="workflow",
    router=router,
    permissions=["approval:submit", "approval:decide"],
    setup=_setup,
)
