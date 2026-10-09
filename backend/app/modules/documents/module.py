from app.modules.documents.application.purge import purge_expired
from app.modules.documents.presentation.router import router
from app.shared.config import settings
from app.shared.modules import ModuleSpec, Schedule

MODULE = ModuleSpec(
    name="documents",
    router=router,
    permissions=["documents:read", "documents:manage", "documents:restore"],
    schedules={"purge_expired": Schedule(purge_expired, settings.PURGE_INTERVAL_SECONDS)},
)
