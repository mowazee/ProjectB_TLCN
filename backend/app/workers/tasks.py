"""Task Celery. R6: worker mỏng - một task chung run_job(job_id) tra handler theo kind."""

import logging
import os
import uuid

from celery import Task

from app.modules.jobs.application.runner import run_job as run
from app.modules.jobs.domain.model import JobOutcome
from app.shared.config import settings
from app.shared.logging import job_id_var
from app.workers.celery_app import WORKER_HOST, celery_app

logger = logging.getLogger(__name__)
WORKER_ID = f"{WORKER_HOST}:{os.getpid()}"


@celery_app.task(name="jobs.run", bind=True, max_retries=None)
def run_job(self: Task, job_id: str) -> str:
    token = job_id_var.set(job_id)
    try:
        outcome = run(uuid.UUID(job_id), worker_id=WORKER_ID)
        logger.info("Job %s kết thúc: %s", job_id, outcome)
        if outcome == JobOutcome.RETRY:
            raise self.retry(countdown=settings.JOB_RETRY_BACKOFF_SECONDS * (self.request.retries + 1))
        return outcome.value
    finally:
        job_id_var.reset(token)


@celery_app.task(name="schedules.run")
def run_schedule(name: str) -> object:
    """Celery beat gọi tác vụ định kỳ theo tên (purge quá hạn, gửi lại job kẹt, nhắc quá hạn mượn)."""
    from app import registry

    for m in registry.enabled_modules():
        if name in m.schedules:
            result = m.schedules[name].fn()
            logger.info("Tác vụ định kỳ %s: %s", name, result)
            return result
    logger.warning("Không có tác vụ định kỳ %s (module có thể đang tắt)", name)
    return None
