"""P2-07 notifications (dùng chung với P2-01): cờ "notifications"; cung cấp Notifier cho lõi."""

from app.modules.notifications.application.service import DbNotifier
from app.modules.notifications.presentation.router import router
from app.shared.modules import ModuleSpec
from app.shared.notify import set_notifier


def _setup() -> None:
    set_notifier(DbNotifier())


MODULE = ModuleSpec(
    name="notifications",
    feature="notifications",
    router=router,
    permissions=["notifications:read"],
    setup=_setup,
)
