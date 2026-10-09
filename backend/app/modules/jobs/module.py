from app.modules.jobs.application.queries import requeue_stuck_jobs
from app.modules.jobs.presentation.router import router
from app.shared.config import settings
from app.shared.modules import ModuleSpec, Schedule

MODULE = ModuleSpec(
    name="jobs",
    router=router,
    permissions=["jobs:read", "jobs:retry"],
    schedules={"requeue_stuck_jobs": Schedule(requeue_stuck_jobs, settings.REQUEUE_INTERVAL_SECONDS)},
)
