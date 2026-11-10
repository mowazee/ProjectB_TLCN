from app.modules.documents.application import validity
from app.modules.documents.application.purge import purge_expired
from app.modules.documents.presentation.router import router
from app.shared import submit_hooks
from app.shared.config import settings
from app.shared.modules import ModuleSpec, Schedule


def _setup() -> None:
    submit_hooks.register(validity.declare_on_submit)  # FR-19: chọn hiệu lực khi gửi duyệt


MODULE = ModuleSpec(
    name="documents",
    router=router,
    permissions=["documents:read", "documents:manage", "documents:restore"],
    schedules={
        "purge_expired": Schedule(purge_expired, settings.PURGE_INTERVAL_SECONDS),
        "validity_tasks": Schedule(validity.run_scheduled, settings.VALIDITY_CHECK_INTERVAL_SECONDS),  # FR-19
    },
    setup=_setup,
)
